"""The Orchestrator brain, reachable over HTTP (the frontend's single entry point).

The canonical Orchestrator (agents/orchestrator.py) is a uAgent on the ASI:One
chat protocol — great for Agentverse, but it can't be called synchronously from
a browser (fire-and-forget message passing, needs a running bureau). This module
runs the SAME brain inline so the web app gets one structured reply per request:

    1. Load the athlete's real context from Supabase (services/athlete_context).
    2. Classify intent with Claude (log / ask / action) — the orchestrator owns
       routing; the frontend never picks an agent.
    3. Route to the matching specialist *analysis function* — the exact same
       Claude functions (agents/common/claude.py) the uAgents call:
          ask         → RAG over the athlete's database history
          recovery    → assess_recovery   (wellness/overtraining, not diagnosis)
          performance → analyze_performance
          sponsorship → suggest_sponsorship (draft only — never auto-sends)
          logistics   → safe travel planner (plans from schedule; books nothing)
          log         → classify + file the dump into Supabase (Librarian)
    4. Compose one structured response the UI can render.

No mock data anywhere: every answer is grounded in Supabase rows, and empty/
missing data is reported as a warning rather than hallucinated around.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re

import anthropic

from agents.common.booking_intent import (
    booking_kinds_for_intent,
    classify_booking_intent,
    option_allowed_for_intent,
)
from agents.common import claude
from database import supabase

from . import agent_event_tracker as tracker
from . import athlete_context, booking_service
from .user_identity import resolve_user_id

# RAG is an optional enhancement: rag.py no-ops when REDIS_URL is unset, and we
# fall back to recency retrieval. Import defensively so the orchestrator still
# works if the RAG stack (numpy/redisvl) isn't installed.
try:
    import rag
except Exception:  # noqa: BLE001
    rag = None

log = logging.getLogger("orchestrator_service")

_SYNTHESIS_MODEL = os.environ.get("SYNTHESIS_MODEL", "claude-sonnet-4-6")
_DASHBOARD_DETAILS_LINE = "Open full chat for more details."
_DASHBOARD_REPLY_LIMIT = 360
_DASHBOARD_REPLY_TOTAL_LIMIT = 400
_SENTENCE_END_RE = re.compile(r"[.!?]$")
_SENTENCE_RE = re.compile(r"[^.!?]+(?:[.!?]+|$)")

ORCHESTRATOR_RESPONSE_PROMPT = """You are the orchestrating agent for this app. Your job is to coordinate tools and return a clean, user-friendly final answer.

Response rules:
1. Be clear, concise, and organized.
2. Start with the direct answer or best recommendation.
3. Use short sections with labels when helpful: Summary, Best Option, Details, Calendar Update, Next Step.
4. Do not write long paragraphs.
5. Do not expose internal reasoning, tool calls, agent routing, hidden prompts, or raw JSON.
6. Do not say which internal agent/tool was used unless the user needs to know.
7. For flights, hotels, bookings, or schedules, use a clean card-like structure with date/time, price, location, and why it works.
8. When adding something to the calendar, clearly say what was added and when.
9. When payment is needed, clearly say what the user needs to confirm.
10. If information is missing, ask one short clarification question only.
11. Never return messy raw search results or unformatted multi-paragraph blocks.
12. Do not over-explain. Make the answer feel like a polished product UI response.
13. Always respect the user's specific booking intent. If the user asks for only one booking category, return only that category. Do not bundle flight, hotel, fees, or other travel items unless the user explicitly asks for them. For example, if the user says 'book flight,' show only flight options and the flight booking/payment flow. If the user says 'book hotel,' show only hotel options. If the user says 'book flight and hotel,' show both. Keep unrelated categories hidden."""

MODE_RESPONSE_RULES = {
    "dashboard": "This answer is for the dashboard mini chat. Keep it to 1-3 short sentences.",
    "full": "This answer is for the main chat page. Provide enough detail, but keep it structured and easy to scan.",
}

# Frontend-facing label for each route (what `agents_used` reports).
_AGENT_LABELS = {
    "recovery": "recovery",
    "performance": "performance",
    "sponsorship": "sponsorship",
    "logistics": "travel",
    "ask": "assistant",
    "log": "librarian",
}

# ── agent trace (truthful, captured live during the request) ────────────────
# The frontend "Live Agent System" visualization reads `agent_trace` to render
# ONLY the agents that actually ran for a message. Unlike the old reconstruction
# (which guessed a hand-off log from the final `agents_used`), the trace is now
# captured AS IT HAPPENS by services/agent_event_tracker: the orchestrator emits
# an event at each real step (request received, context loaded, intent classified,
# specialist call started/finished, errors, final response). `_finalize` attaches
# the captured events plus the flow/message ids to every response.
#
# Payment/calendar stages happen in booking_service.confirm_checkout across the
# Stripe return flow and now emit their own backend trace for the frontend to
# replay when checkout verification completes.


def _finalize(response: dict, tr: tracker.AgentEventTracker | None, mode: str) -> dict:
    """Attach the live-captured trace + ids, then apply the response mode.

    Emits the terminal `final_response_completed` event if no route reached it
    yet — so EVERY path (early returns, intent/route errors) closes the live SSE
    stream and settles the graph, not just the happy path."""
    if tr is not None:
        if tr.ended_at is None:
            tr.final_response("Answer ready")
        response["agent_trace"] = tr.get_trace()
        response["agentTrace"] = response["agent_trace"]
        response["flowId"] = tr.flow_id
        response["messageId"] = tr.message_id
    return _apply_response_mode(response, mode)


def _response_mode(response_mode: str | None, context: dict | None) -> str:
    context_mode = None
    if isinstance(context, dict):
        context_mode = context.get("response_mode") or context.get("chat_mode") or context.get("surface")
    mode = str(response_mode or context_mode or "full").strip().lower()
    return "dashboard" if mode == "dashboard" else "full"


def _style_prompt(mode: str) -> str:
    return f"{ORCHESTRATOR_RESPONSE_PROMPT}\n\n{MODE_RESPONSE_RULES.get(mode, MODE_RESPONSE_RULES['full'])}"


def _money(cents: int | float | None, currency: str = "usd") -> str:
    amount = (float(cents or 0) / 100)
    return f"{currency.upper()} {amount:,.2f}"


def _date_time(start_date=None, start_time=None, end_date=None, end_time=None) -> str:
    start = " ".join(str(v) for v in (start_date, start_time) if v)
    end = " ".join(str(v) for v in (end_date, end_time) if v)
    if start and end and end != start:
        return f"{start} to {end}"
    return start or end or "TBD"


def _short_text(value, limit: int = 140) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        return "Not specified."
    return _truncate_at_word(text, limit)


def _display_label(key: str) -> str:
    return str(key).replace("_", " ").replace("-", " ").title()


def _format_structured_payload(value) -> str:
    if isinstance(value, dict):
        summary = (
            value.get("summary")
            or value.get("message")
            or value.get("answer")
            or value.get("recommendation")
            or value.get("result")
            or "Here is the result."
        )
        lines = ["Summary", _short_text(summary, 220)]
        detail_lines: list[str] = []
        skip = {"summary", "message", "answer", "recommendation", "result", "raw", "metadata"}
        for key, item in value.items():
            if key in skip or item in (None, "", [], {}):
                continue
            if isinstance(item, dict):
                nested = (
                    item.get("summary")
                    or item.get("title")
                    or item.get("name")
                    or item.get("message")
                    or f"{len(item)} fields"
                )
                detail_lines.append(f"* {_display_label(key)}: {_short_text(nested, 140)}")
            elif isinstance(item, list):
                detail_lines.append(
                    f"* {_display_label(key)}: {len(item)} item" + ("" if len(item) == 1 else "s")
                )
            else:
                detail_lines.append(f"* {_display_label(key)}: {_short_text(item, 140)}")
            if len(detail_lines) >= 6:
                break
        if detail_lines:
            lines += ["", "Details", *detail_lines]
        return "\n".join(lines)

    if isinstance(value, list):
        if not value:
            return "Summary\nNo results found."
        lines = ["Summary", f"Found {len(value)} result" + ("" if len(value) == 1 else "s") + ".", "", "Details"]
        for item in value[:6]:
            if isinstance(item, dict):
                title = item.get("title") or item.get("name") or item.get("summary") or item.get("message")
                if not title:
                    keys = ", ".join(_display_label(k) for k in list(item.keys())[:3])
                    title = f"Result with {keys or len(item)}"
                lines.append(f"* {_short_text(title, 150)}")
            else:
                lines.append(f"* {_short_text(item, 150)}")
        return "\n".join(lines)

    return _short_text(value, 800)


def _readable_message(message) -> str:
    if isinstance(message, (dict, list)):
        return _format_structured_payload(message)
    text = str(message or "").strip()
    if not text:
        return ""
    if text[:1] in {"{", "["}:
        try:
            return _format_structured_payload(json.loads(text))
        except json.JSONDecodeError:
            return text
    return text


def _truncate_at_word(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    clipped = re.sub(r"\s+\S*$", "", text[:limit]).strip(" ,:;")
    return clipped or text[:limit].strip()


def _compact_dashboard_message(message: str) -> str:
    stripped = re.sub(
        r"(?im)^(summary|best option|details|calendar plan|calendar update|other options|draft email|next step)\s*$",
        "",
        str(message or ""),
    )
    stripped = re.sub(r"(?m)^\s*\*\s+", "", stripped)
    text = " ".join(stripped.split())
    if not text:
        return message

    sentences = [s.strip() for s in _SENTENCE_RE.findall(text) if s.strip()] or [text]
    picked = " ".join(sentences[:3]).strip()
    needs_more = len(sentences) > 3 or len(text) > _DASHBOARD_REPLY_LIMIT or len(text) > len(picked)
    limit = (
        _DASHBOARD_REPLY_TOTAL_LIMIT - len(_DASHBOARD_DETAILS_LINE) - 2
        if needs_more
        else _DASHBOARD_REPLY_LIMIT
    )
    reply = _truncate_at_word(picked, limit)
    if not _SENTENCE_END_RE.search(reply):
        reply += "."
    if needs_more and "open full chat" not in reply.lower():
        reply += f" {_DASHBOARD_DETAILS_LINE}"
    return reply


def _apply_response_mode(response: dict, mode: str) -> dict:
    if mode != "dashboard":
        return response
    compacted = dict(response)
    compacted["message"] = _compact_dashboard_message(str(compacted.get("message") or ""))
    if isinstance(compacted.get("suggested_actions"), list):
        compacted["suggested_actions"] = compacted["suggested_actions"][:2]
    return compacted


# ── frontend session calendar merge ─────────────────────────────────────────

def _normalize_frontend_event(event: dict | None) -> dict | None:
    if not isinstance(event, dict):
        return None
    start_date = event.get("startDate") or event.get("start_date") or event.get("date")
    start_time = event.get("startTime") or event.get("start_time")
    return {
        "id": event.get("id"),
        "title": event.get("title") or "Calendar event",
        "event_type": event.get("type") or event.get("event_type") or "event",
        "date": start_date,
        "start_time": start_date if start_date else start_time,
        "end_time": event.get("endDate") or event.get("end_date") or event.get("endTime") or event.get("end_time"),
        "location": event.get("location"),
        "source": event.get("source") or "frontend-session",
        "metadata": {
            "start_time_label": start_time,
            "end_time_label": event.get("endTime") or event.get("end_time"),
        },
    }


def _merge_frontend_calendar(ctx: dict, context: dict | None) -> None:
    calendar = (context or {}).get("calendar") if isinstance(context, dict) else None
    if not isinstance(calendar, dict):
        return

    events: list[dict] = []
    seen: set[str] = set()
    current_match = _normalize_frontend_event(calendar.get("currentMatch") or calendar.get("current_match"))

    for raw in [current_match, *(calendar.get("events") or [])]:
        normalized = raw if raw is current_match else _normalize_frontend_event(raw)
        if not normalized:
            continue
        key = str(normalized.get("id") or f"{normalized.get('title')}-{normalized.get('date')}")
        if key in seen:
            continue
        seen.add(key)
        events.append(normalized)

    if not events:
        return

    ctx["_frontend_calendar"] = {
        "currentMatch": current_match,
        "events": events,
    }
    ctx["schedule"] = events + list(ctx.get("schedule") or [])

    travel_types = {"tournament", "match", "travel", "competition", "away"}
    travel_events = [e for e in events if str(e.get("event_type") or "").lower() in travel_types]
    travel = dict(ctx.get("travel") or {})
    travel["trips"] = travel_events + list(travel.get("trips") or [])
    destinations = {d for d in (travel.get("destinations") or []) if d}
    destinations.update(e.get("location") for e in travel_events if e.get("location"))
    travel["destinations"] = sorted(destinations)
    ctx["travel"] = travel


# ── response envelope ───────────────────────────────────────────────────────

def _envelope(
    message: str,
    *,
    intent: str,
    booking_intent: str = "general",
    agents: list[str] | None = None,
    ctx_summary: str = "",
    warnings: list[str] | None = None,
    suggested: list[str] | None = None,
    sources: list | None = None,
    options: list | None = None,
    trace: list | None = None,
) -> dict:
    """The single structured shape the frontend renders."""
    return {
        "message": _readable_message(message),
        "intent": intent,
        "bookingIntent": booking_intent,
        "booking_intent": booking_intent,
        "agents_used": agents or ["orchestrator"],
        # Ordered runtime trace for the Live Agent visualization. Captured live by
        # the event tracker and attached centrally in `_finalize`.
        "agent_trace": trace if trace is not None else [],
        "flowId": None,
        "messageId": None,
        "athlete_context_summary": ctx_summary,
        "warnings": warnings or [],
        "suggested_actions": suggested or [],
        "sources": sources or [],
        "options": options or [],  # bookable travel options (Stripe checkout)
    }


# ── ask path: RAG over athlete database records (shared with POST /chat) ─────

def answer_question(user_id: str, question: str, response_mode: str = "full") -> dict:
    """Retrieve the athlete's most relevant database records and answer from them only.
    Returns {answer, sources, cache_hit}. Used by both the orchestrator's 'ask'
    route and the standalone POST /chat endpoint."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    cached = rag.cache_get(question, user_id) if rag else None
    if cached:
        return {"answer": cached, "sources": [], "cache_hit": True}

    records = rag.retrieve(question, user_id, top_k=8) if rag else []
    if not records:
        # RAG/Redis returned nothing (not configured, unreachable, or the index
        # hasn't been back-filled yet) — fall back to reading the athlete's
        # entries straight from Supabase before giving up.
        records = athlete_context.get_athlete_notes(user_id, limit=15)
    if not records:
        return {
            "answer": (
                "Summary\n"
                "I do not have enough backend history yet to answer that.\n\n"
                "Next Step\n"
                "Log a few practices or matches, then ask again."
            ),
            "sources": [],
            "cache_hit": False,
        }

    def _entry_id(e: dict):
        return e.get("entry_id") or e.get("id")

    if not api_key:
        return {
            "answer": (
                "Summary\n"
                "I found recent backend records, but AI synthesis is not available because ANTHROPIC_API_KEY is not configured.\n\n"
                "Next Step\n"
                "Set ANTHROPIC_API_KEY on the backend to turn analysis back on."
            ),
            "sources": [_entry_id(e) for e in records[:5]],
            "cache_hit": False,
        }

    context = "\n\n".join(
        f"[{(e.get('section') or '').upper()} · {e.get('source_table') or 'database'}]\n{e.get('text') or ''}"
        for e in records
    )
    prompt = (
        "You are a sports performance analyst reviewing an athlete's database history. "
        "Answer using ONLY the records below. Be specific and cite concrete dates, opponents, scores, "
        "metrics, or notes when present. If the records lack enough information, say so. "
        "Return only the final answer shown to the user.\n\n"
        f"ATHLETE DATABASE RECORDS:\n{context}\n\nQUESTION: {question}"
    )
    resp = anthropic.Anthropic().messages.create(
        model=_SYNTHESIS_MODEL,
        max_tokens=800,
        system=_style_prompt(response_mode),
        messages=[{"role": "user", "content": prompt}],
    )
    answer = next((b.text for b in resp.content if b.type == "text"), "")
    if rag:
        rag.cache_set(question, user_id, answer)
    return {"answer": answer, "sources": [_entry_id(e) for e in records], "cache_hit": False}


# ── main entry point ────────────────────────────────────────────────────────

async def run_orchestrator(
    user_id: str,
    message: str,
    session_id: str | None = None,
    flow_id: str | None = None,
    message_id: str | None = None,
    response_mode: str | None = None,
    system_instruction: str | None = None,
    context: dict | None = None,
) -> dict:
    """Receive a raw chat request, ground it in Supabase, route it, answer once.

    Every real step is emitted to the per-request event tracker as it happens, so
    the returned `agent_trace` is a truthful runtime log (not a reconstruction).
    """
    message = (message or "").strip()
    mode = _response_mode(response_mode, context)
    # One flow per message: the tracker collects events live and is cleared when
    # the request finishes. Module-level convenience fns resolve it via contextvar.
    tr = tracker.start_flow(user_id, message_id=message_id, session_id=session_id, flow_id=flow_id)
    try:
        if not message:
            return _finalize(_envelope("Please type a message.", intent="none"), tr, mode)
        tracker.request_received("Request received")
        tracker.orchestrator_started("Orchestrator started")
        if not system_instruction and isinstance(context, dict):
            system_instruction = context.get("system_instruction")

        # 1. Real athlete context from Supabase (off the event loop — sync client).
        ctx = await tracker.track_agent_call(
            from_agent="orchestrator",
            to_agent="athlete_context",
            step="Loading your athlete history",
            call=lambda: asyncio.to_thread(athlete_context.load_athlete_context, user_id),
        )
        _merge_frontend_calendar(ctx, context)
        ctx_summary, warnings = athlete_context.summarize_context(ctx)
        log.info("orchestrator user=%s session=%s page=%s mode=%s instruction=%s | %s",
                 user_id, session_id, (context or {}).get("page"), mode,
                 "yes" if system_instruction else "no", ctx_summary)

        if not os.environ.get("ANTHROPIC_API_KEY"):
            tracker.orchestrator_error("AI analysis unavailable — no API key configured")
            return _finalize(_envelope(
                "AI analysis isn't available yet — the backend has no ANTHROPIC_API_KEY "
                "configured. Your data is still being stored and can be analyzed once a "
                "key is set.",
                intent="none", agents=["orchestrator"], ctx_summary=ctx_summary,
                warnings=warnings + ["ANTHROPIC_API_KEY is not set on the server."],
            ), tr, mode)

        # 2. Intent classification — routing is the orchestrator's job, not the UI's.
        tracker.orchestrator_step("Classifying your intent", "in_progress")
        try:
            intent = await claude.classify_intent(message)
        except Exception as e:  # noqa: BLE001
            log.exception("intent classification failed")
            tracker.orchestrator_error("Could not understand the request",
                                       errorType=type(e).__name__)
            return _finalize(_envelope(
                "I had trouble understanding that — could you rephrase?",
                intent="error", agents=["orchestrator"], ctx_summary=ctx_summary,
                warnings=warnings + [f"intent classification error: {e}"],
            ), tr, mode)

        kind, agent = intent.get("intent"), intent.get("agent")
        booking_intent = classify_booking_intent(message, intent.get("bookingIntent"))
        tracker.orchestrator_decision(
            "Routing decision made",
            intent=str(kind or "unknown"),
            targetAgent=str(agent or "none"),
            bookingIntent=booking_intent,
        )
        log.info("intent=%s agent=%s booking_intent=%s", kind, agent, booking_intent)

        # 3. Route. Each route emits its own agent_started/agent_completed events
        #    around the real specialist call (see _route_* below).
        try:
            if kind == "ask":
                response = await _route_ask(user_id, message, ctx, ctx_summary, warnings, mode)
            elif kind == "action" and agent not in (None, "none"):
                response = await _route_action(user_id, message, agent, ctx, ctx_summary, warnings, booking_intent)
            else:
                response = await _route_log(user_id, message, ctx_summary, warnings)
            tracker.final_response_started("Composing your answer")
            tracker.final_response("Final response sent")
            return _finalize(response, tr, mode)
        except Exception as e:  # noqa: BLE001 — never 500 the chat; degrade cleanly
            log.exception("route failed (intent=%s agent=%s)", kind, agent)
            tracker.orchestrator_error("Something went wrong while analyzing that",
                                       errorType=type(e).__name__)
            return _finalize(_envelope(
                "Something went wrong while analyzing that. Please try again.",
                intent=kind or "error", agents=["orchestrator"], ctx_summary=ctx_summary,
                warnings=warnings + [f"routing error: {e}"],
            ), tr, mode)
    finally:
        tracker.clear_flow(tr)


# ── routes ──────────────────────────────────────────────────────────────────

async def _route_ask(user_id, message, ctx, ctx_summary, warnings, mode: str = "full") -> dict:
    res = await tracker.track_agent_call(
        from_agent="orchestrator",
        to_agent="assistant",
        step="Searching your athlete history",
        call=lambda: asyncio.to_thread(answer_question, user_id, message, mode),
        inputChars=len(message),
    )
    return _envelope(
        res.get("answer") or "I couldn't find an answer for that.",
        intent="ask", agents=[_AGENT_LABELS["ask"]], ctx_summary=ctx_summary,
        warnings=warnings, sources=res.get("sources") or [],
        suggested=["How's my recovery looking?", "Summarize my recent form"],
    )


# ── real specialist-to-specialist chaining ──────────────────────────────────
# The canonical uAgents chain across specialists: Recovery fans out to Fitness +
# Coaching on a physical flag, and Coaching chains to Fitness for a conditioning
# gap (see agents/recovery.py, agents/coaching.py). The HTTP orchestrator runs
# those SAME chains inline so a single chat message lights up the real
# multi-agent graph — not just Orchestrator→one specialist. Every hop is a real
# Claude call wrapped in track_agent_call(from→to), so the inter-agent edges
# stream to the Live Agent visualization the instant they happen.

def _coaching_entries(ctx: dict) -> list[dict]:
    return [e for e in (ctx.get("entries") or []) if e.get("section") == "coaching"]


def _with_addenda(message: str, addenda: list[tuple[str, str]]) -> str:
    """Append the chained specialists' contributions as short labeled sections so
    the multi-agent work is reflected in the answer, not just the visualization."""
    if not addenda:
        return message
    return message + "\n\n" + "\n\n".join(f"{label}\n{text}" for label, text in addenda if text)


async def _chain_fitness(ctx: dict, note: str, recovery_verdict: dict | None, frm: str) -> dict:
    """Run the Fitness specialist as a real chained call (frm → fitness)."""
    plan = await tracker.track_agent_call(
        from_agent=frm,
        to_agent="fitness",
        step="Adjusting the training plan",
        call=lambda: claude.suggest_fitness_plan(
            note, ctx.get("training") or [], ctx.get("recovery_logs") or [],
            ctx.get("entries") or [], recovery_verdict or {},
        ),
    )
    await asyncio.to_thread(
        _persist_output, ctx["user_id"], "Fitness Agent", "training",
        plan.get("summary", ""), "info", plan.get("recommended_action", ""),
    )
    return plan


async def _chain_coaching(ctx: dict, message: str, context_type: str,
                          recovery_verdict: dict | None, frm: str) -> dict:
    """Run the Coaching specialist (frm → coaching); on a physical gap, Coaching
    chains on to Fitness (coaching → fitness)."""
    verdict = await tracker.track_agent_call(
        from_agent=frm,
        to_agent="coaching",
        step="Coordinating coaching strategy",
        call=lambda: claude.coach_strategy(
            context_type, message, _coaching_entries(ctx), ctx.get("matches") or [], recovery_verdict
        ),
    )
    await asyncio.to_thread(
        _persist_output, ctx["user_id"], "Coaching Agent", "coaching",
        verdict.get("summary", ""),
        "medium" if context_type == "injury_accommodation" else "info",
        verdict.get("recommended_action", ""),
    )
    focus = str(verdict.get("fitness_focus") or "").strip()
    if focus:
        try:
            await _chain_fitness(ctx, f"Build targeted conditioning for: {focus}.", recovery_verdict, "coaching")
        except Exception:  # noqa: BLE001 — a chain hop must never break the answer
            log.exception("coaching→fitness chain failed")
    return verdict


async def _route_action(user_id, message, agent, ctx, ctx_summary, warnings, booking_intent: str = "general") -> dict:
    if agent == "recovery":
        v = await tracker.track_agent_call(
            from_agent="orchestrator",
            to_agent="recovery",
            step="Assessing recovery & overtraining signals",
            call=lambda: claude.assess_recovery(
                message, ctx["entries"], ctx["recovery_logs"], ctx["training"], ctx["metrics"]
            ),
        )
        await asyncio.to_thread(_persist_output, user_id, "Recovery Agent", "recovery",
                                v.get("summary", ""), v.get("severity", "info"),
                                v.get("recommended_action", ""))

        # Real agent chain (mirrors agents/recovery.py): a medium/high physical flag
        # fans out to Fitness (adjust the plan) AND Coaching (accommodate the injury)
        # — run concurrently, exactly as the uAgent fires them — and Coaching can
        # chain on to Fitness for a conditioning gap. Each hop is a real Claude call
        # wrapped in track_agent_call, so the Live Agent graph streams the true
        # Recovery→Fitness, Recovery→Coaching, Coaching→Fitness edges as they happen.
        agents_used = ["recovery"]
        addenda: list[tuple[str, str]] = []
        risk = str(v.get("risk_level") or "none").lower()
        if risk in ("medium", "high"):
            fitness_res, coaching_res = await asyncio.gather(
                _chain_fitness(ctx, "Adjust next week's plan around this recovery flag.", v, "recovery"),
                _chain_coaching(ctx, message, "injury_accommodation", v, "recovery"),
                return_exceptions=True,
            )
            if isinstance(fitness_res, dict):
                agents_used.append("fitness")
                if fitness_res.get("summary"):
                    addenda.append(("Training Adjustment", _short_text(fitness_res.get("summary"), 170)))
            elif isinstance(fitness_res, Exception):
                log.warning("recovery→fitness chain failed: %s", fitness_res)
            if isinstance(coaching_res, dict):
                agents_used.append("coaching")
                if str(coaching_res.get("fitness_focus") or "").strip():
                    agents_used.append("fitness")
                advice = coaching_res.get("tactical_advice") or coaching_res.get("summary")
                if advice:
                    addenda.append(("Strategy Tweak", _short_text(advice, 170)))
            elif isinstance(coaching_res, Exception):
                log.warning("recovery→coaching chain failed: %s", coaching_res)

        return _envelope(
            _with_addenda(_format_recovery(v), addenda),
            intent="action", agents=list(dict.fromkeys(agents_used)),
            ctx_summary=ctx_summary, warnings=warnings,
            suggested=["What should I change in training this week?", "Find me an upcoming event"],
        )

    if agent == "performance":
        v = await tracker.track_agent_call(
            from_agent="orchestrator",
            to_agent="performance",
            step="Analyzing performance trends",
            call=lambda: claude.analyze_performance(
                message, ctx["matches"], ctx["training"], ctx["metrics"]
            ),
        )
        await asyncio.to_thread(_persist_output, user_id, "Performance Agent", "performance",
                                v.get("summary", ""), "info", v.get("recommended_focus", ""))

        # Real chain (agents/coaching.py performance_gap): a weak area or declining
        # trend routes Performance→Coaching, which may chain Coaching→Fitness.
        agents_used = ["performance"]
        addenda = []
        weak = str(v.get("weakest_area") or "").strip()
        if weak or str(v.get("trend") or "").lower() == "declining":
            try:
                adv = await _chain_coaching(ctx, message, "performance_gap", None, "performance")
                agents_used.append("coaching")
                if str(adv.get("fitness_focus") or "").strip():
                    agents_used.append("fitness")
                advice = adv.get("tactical_advice") or adv.get("summary")
                if advice:
                    addenda.append(("Coaching Focus", _short_text(advice, 170)))
            except Exception:  # noqa: BLE001 — a chain hop must never break the answer
                log.exception("performance→coaching chain failed")

        return _envelope(
            _with_addenda(_format_performance(v), addenda),
            intent="action", agents=list(dict.fromkeys(agents_used)),
            ctx_summary=ctx_summary, warnings=warnings,
            suggested=["Where am I losing points?", "Am I overtraining?"],
        )

    if agent == "sponsorship":
        media = [e for e in (ctx.get("entries") or []) if e.get("section") == "media_notes"]
        v = await tracker.track_agent_call(
            from_agent="orchestrator",
            to_agent="sponsorship",
            step="Finding sponsor fit and drafting outreach",
            call=lambda: claude.suggest_sponsorship(
                message, ctx["profile"], ctx["matches"], ctx["metrics"], media
            ),
        )
        await asyncio.to_thread(_persist_sponsorship, user_id, v)
        return _envelope(
            _format_sponsorship(v), intent="action", agents=[_AGENT_LABELS["sponsorship"]],
            ctx_summary=ctx_summary, warnings=warnings,
            suggested=["Make the email shorter", "Find another sponsor fit"],
        )

    if agent == "logistics":
        response = await tracker.track_agent_call(
            from_agent="orchestrator",
            to_agent="logistics",
            step="Planning travel and booking options",
            call=lambda: _plan_travel(ctx, ctx_summary, warnings, booking_intent),
        )
        return response

    # Unrecognized specialist — fall back to answering from the journal.
    return await _route_ask(user_id, message, ctx, ctx_summary, warnings)


async def _route_log(user_id, message, ctx_summary, warnings) -> dict:
    entries = await tracker.track_agent_call(
        from_agent="orchestrator",
        to_agent="librarian",
        step="Classifying and filing your note",
        call=lambda: claude.classify(message),
    )
    if not entries:
        return _envelope(
            "Summary\n"
            "I did not find enough detail to file that note.\n\n"
            "Next Step\n"
            "Add the practice, match, recovery, or schedule detail you want saved.",
            intent="log", agents=[_AGENT_LABELS["log"]], ctx_summary=ctx_summary, warnings=warnings,
        )
    await asyncio.to_thread(_store_entries, user_id, entries)
    sections = sorted({e["section"] for e in entries})
    lines = [
        "Summary",
        f"Filed {len(entries)} " + ("entry" if len(entries) == 1 else "entries") + " from your note.",
        "",
        "Details",
    ]
    lines += [f"* {e['section'].replace('_', ' ').title()}: {_short_text(e.get('text'), 110)}" for e in entries]
    lines += [
        "",
        "Next Step",
        "Ask what changed in your recovery, performance, or schedule.",
    ]
    return _envelope(
        "\n".join(lines), intent="log", agents=[_AGENT_LABELS["log"]],
        ctx_summary=ctx_summary, warnings=warnings, suggested=_suggested_after_log(sections),
    )


# ── travel: plan only, never book (task §7 / safety §10) ────────────────────

def _flight_route(option: dict, location: str) -> str:
    return option.get("route") or f"Home airport to {location}"


def _format_flight_options(options: list[dict], location: str) -> str:
    lines = ["Flight Options"]
    for idx, option in enumerate(options, start=1):
        lines += [
            f"Option {idx}",
            f"* Date/time: {_date_time(option.get('start_date'), option.get('start_time'), option.get('end_date'), option.get('end_time'))}",
            f"* Route: {_flight_route(option, location)}",
            f"* Airline: {option.get('airline') or option.get('provider') or 'SportsMom Travel'}",
            f"* Price: {_money(option.get('amount_cents'), option.get('currency', 'usd'))}",
            f"* Why it works: {_short_text(option.get('description'), 140)}",
        ]
    lines += ["", "Next Step", "Choose a flight to continue to payment."]
    return "\n".join(lines)


def _format_hotel_options(options: list[dict], location: str) -> str:
    lines = ["Hotel Options"]
    for idx, option in enumerate(options, start=1):
        lines += [
            f"Option {idx}",
            f"* Check-in: {_date_time(option.get('start_date'), option.get('start_time'))}",
            f"* Check-out: {_date_time(option.get('end_date'), option.get('end_time'))}",
            f"* Location: {option.get('location') or location}",
            f"* Price: {_money(option.get('amount_cents'), option.get('currency', 'usd'))}",
            f"* Why it works: {_short_text(option.get('description'), 140)}",
        ]
    lines += ["", "Next Step", "Choose a hotel to continue to payment."]
    return "\n".join(lines)


def _format_fee_summary(ctx) -> str:
    fee = booking_service.representative_fee_summary(ctx)
    currency = fee.get("currency", "usd")
    return "\n".join([
        "Fee Summary",
        f"* Base price: {_money(fee.get('base_price_cents'), currency)}",
        f"* Service fee: {_money(fee.get('service_fee_cents'), currency)}",
        f"* Total: {_money(fee.get('total_cents'), currency)}",
    ])


def _plan_travel(ctx, ctx_summary, warnings, booking_intent: str = "general") -> dict:
    booking_intent = classify_booking_intent(None, booking_intent)
    if booking_intent == "fee_only":
        return _envelope(
            _format_fee_summary(ctx), intent="action", booking_intent=booking_intent,
            agents=[_AGENT_LABELS["logistics"]],
            ctx_summary=ctx_summary, warnings=warnings,
            suggested=[],
            options=[],
        )

    travel = ctx.get("travel") or {}
    trips = travel.get("trips") or []
    plan = booking_service.travel_plan_from_context(ctx)
    kinds = booking_kinds_for_intent(booking_intent)
    options = [
        option for option in booking_service.representative_options(ctx, kinds)
        if option_allowed_for_intent(option.get("kind"), booking_intent)
    ]
    trip = plan.get("trip") or (trips[0] if trips else None)
    match_date = plan.get("match_date")
    location = plan.get("location") or ""

    if not trip or not match_date or location in {"", "Match Location"}:
        return _envelope(
            "Summary\n"
            "I can help plan travel, but I need the event details first.\n\n"
            "Next Step\n"
            "What date and location should I use?",
            intent="action", booking_intent=booking_intent, agents=[_AGENT_LABELS["logistics"]],
            ctx_summary=ctx_summary, warnings=warnings,
            suggested=["Add my next tournament to the calendar"],
            options=[],
        )

    if booking_intent == "flight_only":
        flight_options = [option for option in options if option.get("kind") == "flight"]
        return _envelope(
            _format_flight_options(flight_options, location),
            intent="action", booking_intent=booking_intent, agents=[_AGENT_LABELS["logistics"]],
            ctx_summary=ctx_summary, warnings=warnings,
            suggested=["Refine departure time", "Pick a different return time"],
            options=flight_options,
        )

    if booking_intent == "hotel_only":
        hotel_options = [option for option in options if option.get("kind") == "hotel"]
        return _envelope(
            _format_hotel_options(hotel_options, location),
            intent="action", booking_intent=booking_intent, agents=[_AGENT_LABELS["logistics"]],
            ctx_summary=ctx_summary, warnings=warnings,
            suggested=["Refine check-in date", "Find a closer room"],
            options=hotel_options,
        )

    if booking_intent == "flight_hotel":
        flight_options = [option for option in options if option.get("kind") == "flight"]
        hotel_options = [option for option in options if option.get("kind") == "hotel"]
        message = "\n\n".join([
            _format_flight_options(flight_options, location),
            _format_hotel_options(hotel_options, location),
        ])
        return _envelope(
            message, intent="action", booking_intent=booking_intent, agents=[_AGENT_LABELS["logistics"]],
            ctx_summary=ctx_summary, warnings=warnings,
            suggested=["Refine flight timing", "Find a closer hotel"],
            options=flight_options + hotel_options,
        )

    best = options[0] if options else None
    lines = [
        "Best Option",
        best.get("title", "Travel option") if best else "Travel plan",
    ]
    if best:
        lines += [
            f"* Date/time: {_date_time(best.get('start_date'), best.get('start_time'), best.get('end_date'), best.get('end_time'))}",
            f"* Price: {_money(best.get('amount_cents'), best.get('currency', 'usd'))}",
            f"* Location: {best.get('location') or location}",
            f"* Why it works: {_short_text(best.get('description'), 120)}",
        ]
    if plan.get("assumption"):
        lines += ["", "Details", f"* {_short_text(plan['assumption'], 150)}"]

    lines += [
        "",
        "Calendar Plan",
        f"* Match: {plan.get('event') or 'Next event'} on {match_date} at {location}",
        f"* Travel: {_date_time(plan.get('travel_date'), None, plan.get('return_date'), None)}",
        f"* Hotel: {plan.get('hotel_nights', 1)} night" + ("" if plan.get("hotel_nights", 1) == 1 else "s"),
    ]

    other_options = options[1:3]
    if other_options:
        lines += ["", "Other Options"]
        for o in other_options:
            lines += [
                o.get("title", "Option"),
                f"* Date/time: {_date_time(o.get('start_date'), o.get('start_time'), o.get('end_date'), o.get('end_time'))}",
                f"* Price: {_money(o.get('amount_cents'), o.get('currency', 'usd'))}",
                f"* Location: {o.get('location') or location}",
                f"* Why it works: {_short_text(o.get('description'), 120)}",
            ]

    lines += ["", "Next Step"]
    lines.append(
        "Choose Book & Pay to review the Stripe payment before anything is charged."
        if booking_service.stripe_configured()
        else "Checkout is not enabled yet. Add STRIPE_SECRET_KEY to Backend/.env before payment."
    )

    extra_warn = (
        [] if booking_service.stripe_configured()
        else ["Stripe key not set — set STRIPE_SECRET_KEY to enable real (test-mode) checkout."]
    )
    return _envelope(
        "\n".join(lines), intent="action", booking_intent=booking_intent, agents=[_AGENT_LABELS["logistics"]],
        ctx_summary=ctx_summary, warnings=warnings + extra_warn,
        suggested=["Add my next tournament to the calendar", "What should I pack?"],
        options=options,
    )


# ── formatting (wellness-safe / approval-gated language) ────────────────────

def _format_recovery(v: dict) -> str:
    parts = ", ".join(v.get("body_parts") or []) or "your body"
    out = (
        "Summary\n"
        f"Recovery signal is {v.get('risk_level', 'unknown')} for {parts}.\n\n"
        "Details\n"
        f"* {_short_text(v.get('summary'), 170)}\n"
        f"* Suggested adjustment: {_short_text(v.get('recommended_action'), 150)}"
    )
    if v.get("pattern_type", "none") not in ("none", ""):
        out += (
            "\n"
            f"* Pattern: {v['pattern_type'].replace('_', ' ')} - "
            f"{_short_text(v.get('pattern_summary'), 150)}"
        )
        if v.get("chain_message"):
            out += f"\n* Follow-up: {_short_text(v.get('chain_message'), 150)}"
    out += (
        "\n\nNext Step\n"
        "Use this as wellness guidance only. If pain persists or worsens, check with a qualified professional."
    )
    return out


def _format_performance(v: dict) -> str:
    return (
        "Summary\n"
        f"Performance trend: {v.get('trend', 'unknown')}.\n\n"
        "Details\n"
        f"* {_short_text(v.get('summary'), 180)}\n"
        f"* Strongest area: {_short_text(v.get('strongest_area'), 90)}\n"
        f"* Work on: {_short_text(v.get('weakest_area'), 90)}\n\n"
        "Next Step\n"
        f"{_short_text(v.get('recommended_focus'), 150)}"
    )


def _format_sponsorship(v: dict) -> str:
    try:
        fit = f"{float(v.get('fit_score', 0)):.2f}"
    except (TypeError, ValueError):
        fit = str(v.get("fit_score", 0))
    return (
        "Summary\n"
        f"Best sponsor fit: {v.get('brand_name', 'Unknown brand')} ({v.get('category', 'category TBD')}), fit {fit}.\n\n"
        "Details\n"
        f"* Why it fits: {_short_text(v.get('reason'), 160)}\n"
        "* Status: Draft created only. Nothing was sent.\n\n"
        "Draft Email\n"
        f"{_short_text(v.get('draft_email'), 650)}\n\n"
        "Next Step\n"
        "Review and approve the draft before sending."
    )


def _suggested_after_log(sections: list[str]) -> list[str]:
    s = set(sections)
    out: list[str] = []
    if {"recovery", "training"} & s:
        out.append("Am I at risk of overtraining?")
    if {"match_results", "performance"} & s:
        out.append("How's my form trending?")
    if "logistics" in s:
        out.append("Help me plan travel for that event")
    return out[:3] or ["What should I focus on next?"]


# ── Supabase writes (real persistence — no fake agent outputs) ──────────────

def _store_entries(user_id: str, entries: list[dict]) -> int:
    resolved_user_id = resolve_user_id(user_id)
    stored = 0
    for e in entries:
        try:
            res = supabase.table("entries").insert({
                "user_id": resolved_user_id, "section": e["section"], "text": e["text"],
                "metadata": {}, "embedded": False,
            }).execute()
            entry_id = (res.data or [{}])[0].get("id")
            try:
                if rag and entry_id and rag.store_entry(entry_id, resolved_user_id, e["section"], e["text"]):
                    supabase.table("entries").update({"embedded": True}).eq("id", entry_id).execute()
            except Exception as ex:  # noqa: BLE001 — embedding is best-effort
                log.debug("embed entry %s failed: %s", entry_id, ex)
            stored += 1
        except Exception as ex:  # noqa: BLE001
            log.warning("store entry failed: %s", ex)
    return stored


def _persist_output(user_id, agent_name, section, summary, severity, recommended_action) -> None:
    try:
        supabase.table("agent_outputs").insert({
            "user_id": user_id, "agent_name": agent_name, "section": section,
            "summary": summary, "severity": severity,
            "recommended_action": recommended_action, "related_entry_ids": [],
        }).execute()
    except Exception as e:  # noqa: BLE001
        log.warning("persist %s output failed: %s", agent_name, e)


def _persist_sponsorship(user_id, v: dict) -> None:
    try:
        supabase.table("sponsorship_opportunities").insert({
            "user_id": user_id, "brand_name": v.get("brand_name", ""),
            "category": v.get("category", ""), "fit_score": v.get("fit_score", 0),
            "reason": v.get("reason", ""), "draft_email": v.get("draft_email", ""),
            "status": "drafted",
        }).execute()
    except Exception as e:  # noqa: BLE001
        log.warning("persist sponsorship failed: %s", e)
