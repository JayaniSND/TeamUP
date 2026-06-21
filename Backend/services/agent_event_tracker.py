"""Agent Event Tracker — a truthful, real-time runtime trace of one chat request.

The Live Agent visualization must reflect *what actually happened*, not a guess
reconstructed from the final answer. This module captures an event AT THE MOMENT
each step runs — request received, athlete context loaded, intent classified,
each specialist call started/finished, errors, and the final response — each with
a real timestamp. The orchestrator emits to it before and after every agent call.

Privacy / safety (task §"Privacy"): events carry ONLY lightweight metadata —
agent names, from/to, a status, a human `step` label, a timestamp, and small
numeric counts (e.g. how many characters the input was, how many sources grounded
the answer). Never prompts, user data, model responses, tokens, database rows, or
payment secrets. `_safe_meta` enforces this at the boundary.

Per-flow isolation uses a ``ContextVar`` so deeply-nested ``emit`` calls attach to
the right flow without threading a tracker object through every function. The
module-level convenience functions (``request_received``, ``agent_started`` …)
resolve the current flow and no-op when there isn't one, so instrumentation never
crashes a request.

SSE / WebSocket ready (task Option A/B, "structure so it can replace this later"):
every flow lives in a bounded module-level registry keyed by ``flow_id`` and each
``_emit`` notifies any subscriber queues. Today ``run_orchestrator`` returns the
full trace with the reply (Phase 1 / Option C). A future streaming endpoint can
``start_flow`` → ``subscribe(flow_id)`` → drain events live, then ``clear_flow`` —
WITHOUT changing a single orchestrator call site.
"""

from __future__ import annotations

import contextvars
import inspect
import logging
import time
import uuid
from typing import Any, Callable

log = logging.getLogger("agent_event_tracker")

# The tracker for the request currently being handled (propagates into
# asyncio.to_thread workers, which copy the context). Default None = no flow.
_current: contextvars.ContextVar["AgentEventTracker | None"] = contextvars.ContextVar(
    "agent_event_tracker", default=None
)

# Bounded registry of live/recent flows so a future SSE endpoint can look one up
# by id. Bounded so a long-running server never leaks flows.
_FLOWS: "dict[str, AgentEventTracker]" = {}
_MAX_FLOWS = 64
_ENDED_FLOW_TTL_MS = 2 * 60 * 1000
_OPEN_FLOW_TTL_MS = 15 * 60 * 1000

# ── event types (mirror the frontend's expectations) ────────────────────────
REQUEST_RECEIVED = "request_received"
ORCHESTRATOR_STARTED = "orchestrator_started"
ORCHESTRATOR_PLAN = "orchestrator_plan"
AGENT_PLANNED = "agent_planned"
ORCHESTRATOR_DECISION = "orchestrator_decision"
ORCHESTRATOR_PROGRESS = "orchestrator_progress"
AGENT_CALL_STARTED = "agent_call_started"
AGENT_REQUEST_SENT = "agent_request_sent"
AGENT_RESPONSE_RECEIVED = "agent_response_received"
AGENT_CALL_COMPLETED = "agent_call_completed"
AGENT_CALL_FAILED = "agent_call_failed"
FINAL_RESPONSE_STARTED = "final_response_started"
FINAL_RESPONSE_COMPLETED = "final_response_completed"
PAYMENT_SESSION_STARTED = "payment_session_started"
PAYMENT_SESSION_COMPLETED = "payment_session_completed"
PAYMENT_VERIFIED = "payment_verified"
CALENDAR_EVENT_CREATED = "calendar_event_created"

_DISPLAY_NAMES = {
    "orchestrator": "OrchestratorAgent",
    "assistant": "ChatAgent",
    "recovery": "RecoveryAgent",
    "performance": "PerformanceAgent",
    "sponsorship": "SponsorshipAgent",
    "logistics": "LogisticsAgent",
    "librarian": "LibrarianAgent",
    "scout": "ScoutAgent",
    "fitness": "FitnessAgent",
    "coaching": "CoachingAgent",
    "payment": "PaymentAgent",
    "calendar": "CalendarAgent",
    "athlete_context": "AthleteContextService",
}


def _agent_name(agent: str | None) -> str | None:
    if not agent:
        return None
    return _DISPLAY_NAMES.get(agent, agent)


def _now_ms() -> int:
    return int(time.time() * 1000)


# Key fragments that must NEVER reach the frontend trace, even as a short scalar.
# _safe_meta already drops large/structured values (prompts, rows, responses);
# this is the second guard so a caller can't leak a secret by passing it under a
# small key (task §"Privacy": no private tokens, prompts, payment/Stripe secrets,
# or PII). Checked against every real call site — drops nothing legitimate.
_SENSITIVE_KEY_PARTS = (
    "token", "secret", "password", "passwd", "apikey", "api_key",
    "authorization", "credential", "cookie", "prompt", "email",
    "ssn", "cvv", "card", "stripe",
)


def _is_sensitive_key(key: str) -> bool:
    k = str(key).lower()
    return any(part in k for part in _SENSITIVE_KEY_PARTS)


def _safe_meta(meta: dict[str, Any] | None) -> dict[str, Any]:
    """Keep only small, non-sensitive scalars. Counts and short labels are fine;
    anything large or structured (prompts, rows, responses) is dropped, and any
    field whose KEY looks sensitive is dropped outright — so a token/secret can
    never reach the frontend trace even if a caller passes one."""
    if not meta:
        return {}
    safe: dict[str, Any] = {}
    for key, value in meta.items():
        if _is_sensitive_key(key):
            continue  # never forward sensitive-looking fields, even short scalars
        if isinstance(value, bool) or isinstance(value, (int, float)):
            safe[str(key)] = value
        elif isinstance(value, str) and len(value) <= 48:
            safe[str(key)] = value
        # everything else (lists, dicts, long strings) is intentionally ignored
    return safe


class AgentEventTracker:
    """Collects the ordered events for a single chat request (one ``flow_id``)."""

    def __init__(
        self,
        user_id: str,
        message_id: str | None = None,
        session_id: str | None = None,
        flow_id: str | None = None,
    ):
        self.flow_id = flow_id or uuid.uuid4().hex
        self.message_id = message_id or uuid.uuid4().hex
        self.session_id = session_id
        self.user_id = user_id
        self.events: list[dict] = []
        self.created_at = _now_ms()
        self.ended_at: int | None = None
        # Subscriber queues for a future SSE/WebSocket layer (Phase 2). Each is an
        # object with a thread-safe `put` (e.g. asyncio.Queue.put_nowait). Empty
        # today, so notification is a no-op and costs nothing.
        self._subscribers: list[Any] = []

    # ── low-level emit ──────────────────────────────────────────────────────
    def _emit(
        self,
        event_type: str,
        *,
        status: str,
        step: str,
        agent: str | None = None,
        frm: str | None = None,
        to: str | None = None,
        **metadata: Any,
    ) -> dict:
        event = {
            "eventId": uuid.uuid4().hex,
            "flowId": self.flow_id,
            "messageId": self.message_id,
            "type": event_type,
            "status": status,
            "step": step,
            "ts": _now_ms(),
        }
        event["timestamp"] = event["ts"]
        # The frontend trace parser keys off agent / from / to — keep those names.
        if agent:
            event["agent"] = agent
            event["agentName"] = _agent_name(agent)
        if frm:
            event["from"] = frm
            event["fromAgent"] = _agent_name(frm)
        if to:
            event["to"] = to
            event["toAgent"] = _agent_name(to)
            if "agentName" not in event:
                event["agentName"] = _agent_name(to)
        duration = metadata.pop("durationMs", None)
        if isinstance(duration, (int, float)):
            event["durationMs"] = int(duration)
        safe = _safe_meta(metadata)
        if safe:
            event["metadata"] = safe
        self.events.append(event)
        self._notify(event)
        return event

    def _notify(self, event: dict) -> None:
        for queue in tuple(self._subscribers):
            try:
                queue.put_nowait(event)
            except Exception as exc:  # noqa: BLE001 — a dead subscriber must not break tracking
                log.debug("agent-event subscriber dropped: %s", exc)
                try:
                    self._subscribers.remove(queue)
                except ValueError:
                    pass

    # ── semantic events (used by the orchestrator) ──────────────────────────
    def request_received(self, step: str = "Request received") -> None:
        self._emit(REQUEST_RECEIVED, status="in_progress", step=step, agent="orchestrator")

    def orchestrator_started(self, step: str = "Orchestrator started") -> None:
        self._emit(ORCHESTRATOR_STARTED, status="in_progress", step=step, agent="orchestrator")

    def orchestrator_step(self, step: str, status: str = "in_progress") -> None:
        self._emit(ORCHESTRATOR_PROGRESS, status=status, step=step, agent="orchestrator")

    def plan(self, agents: "list[str]", step: str = "Planning which agents to use") -> None:
        """Announce, BEFORE any real call, which agents the orchestrator expects to
        use. Emits one `agent_planned` edge (orchestrator → agent, status="planned")
        per predicted agent so the Live Agent graph can render the whole network up
        front and then animate each node as the real calls actually happen."""
        self._emit(ORCHESTRATOR_PLAN, status="planned", step=step, agent="orchestrator",
                   plannedCount=len(agents))
        for target in agents:
            if not target or target == "orchestrator":
                continue
            self._emit(AGENT_PLANNED, status="planned",
                       step=f"{_agent_name(target) or target} ready", frm="orchestrator",
                       to=target, agent=target)

    def orchestrator_decision(self, step: str, **metadata: Any) -> None:
        self._emit(ORCHESTRATOR_DECISION, status="completed", step=step, agent="orchestrator", **metadata)

    def orchestrator_error(self, step: str, **metadata: Any) -> None:
        self._emit(AGENT_CALL_FAILED, status="error", step=step, agent="orchestrator", **metadata)

    def agent_started(self, agent: str, step: str, frm: str = "orchestrator", **metadata: Any) -> None:
        self._emit(
            AGENT_CALL_STARTED, status="in_progress", step=step, frm=frm, to=agent, agent=agent, **metadata
        )
        self._emit(
            AGENT_REQUEST_SENT,
            status="in_progress",
            step=f"Request metadata sent to {_agent_name(agent) or agent}",
            frm=frm,
            to=agent,
            agent=agent,
            **metadata,
        )

    def agent_completed(self, agent: str, step: str, frm: str = "orchestrator", **metadata: Any) -> None:
        self._emit(
            AGENT_RESPONSE_RECEIVED, status="completed", step=step, frm=agent, to=frm, agent=agent, **metadata
        )

    def agent_done(self, agent: str, step: str, **metadata: Any) -> None:
        self._emit(AGENT_CALL_COMPLETED, status="completed", step=step, agent=agent, **metadata)

    def agent_error(self, agent: str, step: str, frm: str = "orchestrator", **metadata: Any) -> None:
        self._emit(AGENT_CALL_FAILED, status="error", step=step, frm=frm, to=agent, agent=agent, **metadata)

    def final_response_started(self, step: str = "Composing your answer") -> None:
        peer = None
        for event in reversed(self.events):
            candidate = event.get("agent")
            if candidate and candidate != "orchestrator":
                peer = candidate
                break
        if peer:
            self._emit(
                FINAL_RESPONSE_STARTED,
                status="in_progress",
                step=step,
                frm=peer,
                to="orchestrator",
                agent="orchestrator",
            )
        else:
            self._emit(FINAL_RESPONSE_STARTED, status="in_progress", step=step, agent="orchestrator")

    def final_response(self, step: str = "Answer ready") -> None:
        self._emit(FINAL_RESPONSE_COMPLETED, status="completed", step=step, agent="orchestrator")
        self.ended_at = _now_ms()

    def payment_session_started(self, step: str = "Creating payment session", **metadata: Any) -> None:
        self._emit(PAYMENT_SESSION_STARTED, status="in_progress", step=step, agent="payment", **metadata)

    def payment_session_completed(self, step: str = "Payment session ready", **metadata: Any) -> None:
        self._emit(PAYMENT_SESSION_COMPLETED, status="completed", step=step, agent="payment", **metadata)

    def payment_verified(self, step: str = "Payment verified", **metadata: Any) -> None:
        self._emit(PAYMENT_VERIFIED, status="completed", step=step, agent="payment", **metadata)

    def calendar_event_created(self, step: str = "Calendar event created", **metadata: Any) -> None:
        self._emit(CALENDAR_EVENT_CREATED, status="completed", step=step, agent="calendar", **metadata)

    # ── accessors ───────────────────────────────────────────────────────────
    def get_trace(self) -> list[dict]:
        """A shallow copy of the ordered events captured for this flow."""
        return list(self.events)

    def subscribe(self, queue: Any) -> None:
        """Register a queue to receive events live (Phase 2 SSE/WebSocket)."""
        self._subscribers.append(queue)

    def unsubscribe(self, queue: Any) -> None:
        try:
            self._subscribers.remove(queue)
        except ValueError:
            pass


# ── module-level flow lifecycle ─────────────────────────────────────────────

def clear_old_flows() -> None:
    now = _now_ms()
    for flow_id, tracker in list(_FLOWS.items()):
        ended = tracker.ended_at is not None and now - tracker.ended_at > _ENDED_FLOW_TTL_MS
        stale = tracker.ended_at is None and now - tracker.created_at > _OPEN_FLOW_TTL_MS
        if ended or stale:
            _FLOWS.pop(flow_id, None)


def start_flow(
    user_id: str,
    message_id: str | None = None,
    session_id: str | None = None,
    flow_id: str | None = None,
) -> AgentEventTracker:
    """Begin a flow, register it, and make it the current context's tracker."""
    clear_old_flows()
    tracker = _FLOWS.get(flow_id) if flow_id else None
    if tracker is None:
        tracker = AgentEventTracker(user_id, message_id=message_id, session_id=session_id, flow_id=flow_id)
    else:
        tracker.user_id = user_id
        tracker.message_id = message_id or tracker.message_id
        tracker.session_id = session_id or tracker.session_id
        tracker.ended_at = None
    # Bound the registry so a long-lived server never leaks flows: when full and
    # this is a genuinely new flow, evict the OLDEST (dict preserves insertion
    # order). Reusing an existing flow_id doesn't grow the registry, so skip then.
    if len(_FLOWS) >= _MAX_FLOWS and tracker.flow_id not in _FLOWS:
        oldest = next(iter(_FLOWS), None)
        if oldest is not None:
            _FLOWS.pop(oldest, None)
    _FLOWS[tracker.flow_id] = tracker
    tracker._token = _current.set(tracker)  # type: ignore[attr-defined]
    return tracker


def clear_flow(tracker: AgentEventTracker | None) -> None:
    """Reset the context var and mark the flow ended; old traces expire shortly."""
    if tracker is None:
        return
    token = getattr(tracker, "_token", None)
    if token is not None:
        try:
            _current.reset(token)
        except ValueError:
            # token belongs to a different context (e.g. cleared in a worker) —
            # fall back to clearing the current var directly.
            _current.set(None)
    tracker.ended_at = tracker.ended_at or _now_ms()
    clear_old_flows()


def current() -> AgentEventTracker | None:
    return _current.get()


def get_flow(flow_id: str) -> AgentEventTracker | None:
    return _FLOWS.get(flow_id)


def ensure_flow(flow_id: str, message_id: str | None = None, user_id: str = "pending") -> AgentEventTracker:
    clear_old_flows()
    existing = _FLOWS.get(flow_id)
    if existing:
        if message_id:
            existing.message_id = message_id
        return existing
    tracker = AgentEventTracker(user_id=user_id, message_id=message_id, flow_id=flow_id)
    _FLOWS[tracker.flow_id] = tracker
    return tracker


def get_flow_trace(flow_id: str) -> list[dict]:
    flow = get_flow(flow_id)
    return flow.get_trace() if flow else []


def emit_agent_event(event: dict[str, Any]) -> dict | None:
    tr = current() or (ensure_flow(str(event["flowId"])) if event.get("flowId") else None)
    if not tr:
        return None
    return tr._emit(
        str(event.get("type") or ORCHESTRATOR_PROGRESS),
        status=str(event.get("status") or "in_progress"),
        step=str(event.get("step") or "Working"),
        agent=event.get("agent") or event.get("agentName"),
        frm=event.get("from") or event.get("fromAgent"),
        to=event.get("to") or event.get("toAgent"),
        **(event.get("metadata") or {}),
    )


# ── convenience wrappers (no-op when there is no current flow) ───────────────
# These let the orchestrator instrument routes without holding a tracker handle:
#   tracker.agent_started("recovery", "Assessing recovery signals")

def request_received(step: str = "Request received") -> None:
    tr = current()
    if tr:
        tr.request_received(step)


def orchestrator_started(step: str = "Orchestrator started") -> None:
    tr = current()
    if tr:
        tr.orchestrator_started(step)


def orchestrator_step(step: str, status: str = "in_progress") -> None:
    tr = current()
    if tr:
        tr.orchestrator_step(step, status)


def orchestrator_decision(step: str, **metadata: Any) -> None:
    tr = current()
    if tr:
        tr.orchestrator_decision(step, **metadata)


def plan(agents: "list[str]", step: str = "Planning which agents to use") -> None:
    tr = current()
    if tr:
        tr.plan(agents, step)


def orchestrator_error(step: str, **metadata: Any) -> None:
    tr = current()
    if tr:
        tr.orchestrator_error(step, **metadata)


def agent_started(agent: str, step: str, **metadata: Any) -> None:
    tr = current()
    if tr:
        tr.agent_started(agent, step, **metadata)


def agent_completed(agent: str, step: str, **metadata: Any) -> None:
    tr = current()
    if tr:
        tr.agent_completed(agent, step, **metadata)


def agent_done(agent: str, step: str, **metadata: Any) -> None:
    tr = current()
    if tr:
        tr.agent_done(agent, step, **metadata)


def agent_error(agent: str, step: str, **metadata: Any) -> None:
    tr = current()
    if tr:
        tr.agent_error(agent, step, **metadata)


def final_response(step: str = "Composing your answer") -> None:
    tr = current()
    if tr:
        tr.final_response(step)


def final_response_started(step: str = "Composing your answer") -> None:
    tr = current()
    if tr:
        tr.final_response_started(step)


def payment_session_started(step: str = "Creating payment session", **metadata: Any) -> None:
    tr = current()
    if tr:
        tr.payment_session_started(step, **metadata)


def payment_session_completed(step: str = "Payment session ready", **metadata: Any) -> None:
    tr = current()
    if tr:
        tr.payment_session_completed(step, **metadata)


def payment_verified(step: str = "Payment verified", **metadata: Any) -> None:
    tr = current()
    if tr:
        tr.payment_verified(step, **metadata)


def calendar_event_created(step: str = "Calendar event created", **metadata: Any) -> None:
    tr = current()
    if tr:
        tr.calendar_event_created(step, **metadata)


async def track_agent_call(
    *,
    from_agent: str,
    to_agent: str,
    step: str,
    call: Callable[[], Any],
    **metadata: Any,
) -> Any:
    """Run one real backend call with consistent activity events around it."""
    started_at = _now_ms()
    agent_started(to_agent, step, frm=from_agent, **metadata)
    try:
        result = call()
        if inspect.isawaitable(result):
            result = await result
        duration = _now_ms() - started_at
        agent_completed(to_agent, f"{step} response received", frm=from_agent, durationMs=duration)
        agent_done(to_agent, f"{step} completed", durationMs=duration)
        return result
    except Exception as exc:  # noqa: BLE001
        duration = _now_ms() - started_at
        agent_error(
            to_agent,
            f"{step} failed",
            frm=from_agent,
            durationMs=duration,
            errorMessage=type(exc).__name__,
        )
        raise


def track_agent_call_sync(
    *,
    from_agent: str,
    to_agent: str,
    step: str,
    call: Callable[[], Any],
    **metadata: Any,
) -> Any:
    """Synchronous variant for FastAPI sync routes and service helpers."""
    started_at = _now_ms()
    agent_started(to_agent, step, frm=from_agent, **metadata)
    try:
        result = call()
        duration = _now_ms() - started_at
        agent_completed(to_agent, f"{step} response received", frm=from_agent, durationMs=duration)
        agent_done(to_agent, f"{step} completed", durationMs=duration)
        return result
    except Exception as exc:  # noqa: BLE001
        duration = _now_ms() - started_at
        agent_error(
            to_agent,
            f"{step} failed",
            frm=from_agent,
            durationMs=duration,
            errorMessage=type(exc).__name__,
        )
        raise
