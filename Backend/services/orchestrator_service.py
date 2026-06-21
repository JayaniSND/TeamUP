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
import logging
import os
import re

import anthropic

from agents.common import claude
from database import supabase

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

# Frontend-facing label for each route (what `agents_used` reports).
_AGENT_LABELS = {
    "recovery": "recovery",
    "performance": "performance",
    "sponsorship": "sponsorship",
    "logistics": "travel",
    "ask": "assistant",
    "log": "librarian",
}


def _response_mode(response_mode: str | None, context: dict | None) -> str:
    context_mode = None
    if isinstance(context, dict):
        context_mode = context.get("response_mode") or context.get("chat_mode") or context.get("surface")
    mode = str(response_mode or context_mode or "full").strip().lower()
    return "dashboard" if mode == "dashboard" else "full"


def _truncate_at_word(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    clipped = re.sub(r"\s+\S*$", "", text[:limit]).strip(" ,:;")
    return clipped or text[:limit].strip()


def _compact_dashboard_message(message: str) -> str:
    text = " ".join(str(message or "").split())
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
    agents: list[str] | None = None,
    ctx_summary: str = "",
    warnings: list[str] | None = None,
    suggested: list[str] | None = None,
    sources: list | None = None,
    options: list | None = None,
) -> dict:
    """The single structured shape the frontend renders."""
    return {
        "message": message,
        "intent": intent,
        "agents_used": agents or ["orchestrator"],
        "athlete_context_summary": ctx_summary,
        "warnings": warnings or [],
        "suggested_actions": suggested or [],
        "sources": sources or [],
        "options": options or [],  # bookable travel options (Stripe checkout)
    }


# ── ask path: RAG over athlete database records (shared with POST /chat) ─────

def answer_question(user_id: str, question: str) -> dict:
    """Retrieve the athlete's most relevant database records and answer from them only.
    Returns {answer, sources, cache_hit}. Used by both the orchestrator's 'ask'
    route and the standalone POST /chat endpoint."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    cached = rag.cache_get(question, user_id) if rag else None
    if cached:
        return {"answer": cached, "sources": [], "cache_hit": True}

    records = rag.retrieve(question, user_id, top_k=8) if rag else athlete_context.get_athlete_notes(user_id, limit=15)
    if not records:
        return {
            "answer": "I don't have any backend records for you yet — log a few "
            "practices or matches and I'll be able to answer from your database history.",
            "sources": [],
            "cache_hit": False,
        }

    def _entry_id(e: dict):
        return e.get("entry_id") or e.get("id")

    if not api_key:
        joined = "; ".join((e.get("text") or "") for e in records[:5])
        return {
            "answer": f"(no ANTHROPIC_API_KEY set) Retrieved backend records: {joined}",
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
        "metrics, or notes when present. If the records lack enough information, say so.\n\n"
        f"ATHLETE DATABASE RECORDS:\n{context}\n\nQUESTION: {question}"
    )
    resp = anthropic.Anthropic().messages.create(
        model=_SYNTHESIS_MODEL,
        max_tokens=800,
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
    response_mode: str | None = None,
    system_instruction: str | None = None,
    context: dict | None = None,
) -> dict:
    """Receive a raw chat request, ground it in Supabase, route it, answer once."""
    message = (message or "").strip()
    if not message:
        return _envelope("Please type a message.", intent="none")
    mode = _response_mode(response_mode, context)
    if not system_instruction and isinstance(context, dict):
        system_instruction = context.get("system_instruction")

    # 1. Real athlete context from Supabase (off the event loop — sync client).
    ctx = await asyncio.to_thread(athlete_context.load_athlete_context, user_id)
    _merge_frontend_calendar(ctx, context)
    ctx_summary, warnings = athlete_context.summarize_context(ctx)
    log.info("orchestrator user=%s session=%s page=%s mode=%s instruction=%s | %s",
             user_id, session_id, (context or {}).get("page"), mode,
             "yes" if system_instruction else "no", ctx_summary)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _apply_response_mode(_envelope(
            "AI analysis isn't available yet — the backend has no ANTHROPIC_API_KEY "
            "configured. Your data is still being stored and can be analyzed once a "
            "key is set.",
            intent="none", agents=["orchestrator"], ctx_summary=ctx_summary,
            warnings=warnings + ["ANTHROPIC_API_KEY is not set on the server."],
        ), mode)

    # 2. Intent classification — routing is the orchestrator's job, not the UI's.
    try:
        intent = await claude.classify_intent(message)
    except Exception as e:  # noqa: BLE001
        log.exception("intent classification failed")
        return _apply_response_mode(_envelope(
            "I had trouble understanding that — could you rephrase?",
            intent="error", agents=["orchestrator"], ctx_summary=ctx_summary,
            warnings=warnings + [f"intent classification error: {e}"],
        ), mode)

    kind, agent = intent.get("intent"), intent.get("agent")
    log.info("intent=%s agent=%s", kind, agent)

    # 3. Route.
    try:
        if kind == "ask":
            response = await _route_ask(user_id, message, ctx, ctx_summary, warnings)
        elif kind == "action" and agent not in (None, "none"):
            response = await _route_action(user_id, message, agent, ctx, ctx_summary, warnings)
        else:
            response = await _route_log(user_id, message, ctx_summary, warnings)
        return _apply_response_mode(response, mode)
    except Exception as e:  # noqa: BLE001 — never 500 the chat; degrade cleanly
        log.exception("route failed (intent=%s agent=%s)", kind, agent)
        return _apply_response_mode(_envelope(
            "Something went wrong while analyzing that. Please try again.",
            intent=kind or "error", agents=["orchestrator"], ctx_summary=ctx_summary,
            warnings=warnings + [f"routing error: {e}"],
        ), mode)


# ── routes ──────────────────────────────────────────────────────────────────

async def _route_ask(user_id, message, ctx, ctx_summary, warnings) -> dict:
    res = await asyncio.to_thread(answer_question, user_id, message)
    return _envelope(
        res.get("answer") or "I couldn't find an answer for that.",
        intent="ask", agents=[_AGENT_LABELS["ask"]], ctx_summary=ctx_summary,
        warnings=warnings, sources=res.get("sources") or [],
        suggested=["How's my recovery looking?", "Summarize my recent form"],
    )


async def _route_action(user_id, message, agent, ctx, ctx_summary, warnings) -> dict:
    if agent == "recovery":
        v = await claude.assess_recovery(
            message, ctx["entries"], ctx["recovery_logs"], ctx["training"], ctx["metrics"]
        )
        await asyncio.to_thread(_persist_output, user_id, "Recovery Agent", "recovery",
                                v.get("summary", ""), v.get("severity", "info"),
                                v.get("recommended_action", ""))
        return _envelope(
            _format_recovery(v), intent="action", agents=[_AGENT_LABELS["recovery"]],
            ctx_summary=ctx_summary, warnings=warnings,
            suggested=["What should I change in training this week?", "Find me an upcoming event"],
        )

    if agent == "performance":
        v = await claude.analyze_performance(
            message, ctx["matches"], ctx["training"], ctx["metrics"]
        )
        await asyncio.to_thread(_persist_output, user_id, "Performance Agent", "performance",
                                v.get("summary", ""), "info", v.get("recommended_focus", ""))
        return _envelope(
            _format_performance(v), intent="action", agents=[_AGENT_LABELS["performance"]],
            ctx_summary=ctx_summary, warnings=warnings,
            suggested=["Where am I losing points?", "Am I overtraining?"],
        )

    if agent == "sponsorship":
        media = [e for e in (ctx.get("entries") or []) if e.get("section") == "media_notes"]
        v = await claude.suggest_sponsorship(
            message, ctx["profile"], ctx["matches"], ctx["metrics"], media
        )
        await asyncio.to_thread(_persist_sponsorship, user_id, v)
        return _envelope(
            _format_sponsorship(v), intent="action", agents=[_AGENT_LABELS["sponsorship"]],
            ctx_summary=ctx_summary, warnings=warnings,
            suggested=["Make the email shorter", "Find another sponsor fit"],
        )

    if agent == "logistics":
        return _plan_travel(ctx, ctx_summary, warnings)

    # Unrecognized specialist — fall back to answering from the journal.
    return await _route_ask(user_id, message, ctx, ctx_summary, warnings)


async def _route_log(user_id, message, ctx_summary, warnings) -> dict:
    entries = await claude.classify(message)
    if not entries:
        return _envelope(
            "I didn't find anything to file in that note — try adding a bit more detail.",
            intent="log", agents=[_AGENT_LABELS["log"]], ctx_summary=ctx_summary, warnings=warnings,
        )
    await asyncio.to_thread(_store_entries, user_id, entries)
    sections = sorted({e["section"] for e in entries})
    lines = [f"📓 Filed {len(entries)} " + ("entry" if len(entries) == 1 else "entries") + ":"]
    lines += [f"  • [{e['section']}] {e['text']}" for e in entries]
    lines.append("Sections: " + ", ".join(sections) + ".")
    return _envelope(
        "\n".join(lines), intent="log", agents=[_AGENT_LABELS["log"]],
        ctx_summary=ctx_summary, warnings=warnings, suggested=_suggested_after_log(sections),
    )


# ── travel: plan only, never book (task §7 / safety §10) ────────────────────

def _plan_travel(ctx, ctx_summary, warnings) -> dict:
    travel = ctx.get("travel") or {}
    trips = travel.get("trips") or []
    plan = booking_service.travel_plan_from_context(ctx)
    options = booking_service.representative_options(ctx)

    lines = ["🧳 Travel & booking"]
    if plan.get("assumption"):
        lines.append(plan["assumption"])
    if trips:
        lines.append("Upcoming away commitments on your calendar:")
        for t in trips[:5]:
            when = t.get("start_time") or t.get("date") or "date TBD"
            lines.append(f"  • {t.get('title', '(event)')} — {t.get('location', '?')} ({when})")
    else:
        lines.append(
            "I don't see any tournaments or away matches on your calendar yet, so I'm "
            "planning around your next event generally. Add a calendar event and I'll "
            "tailor flights, hotels, and entry to it."
        )

    if options:
        lines.append("")
        lines.append("Pick an option below to book and pay securely:")
        for o in options:
            lines.append(f"  • {o['title']} — ${o['amount_cents'] / 100:.2f}")

    lines.append("")
    lines.append(
        "Payments run through Stripe — you'll review the amount on Stripe's secure "
        "page and confirm before anything is charged."
        if booking_service.stripe_configured()
        else "Note: checkout isn't enabled yet (no Stripe key set), so the Book buttons "
        "will tell you what's needed rather than charge anything."
    )

    extra_warn = (
        [] if booking_service.stripe_configured()
        else ["Stripe key not set — set STRIPE_SECRET_KEY to enable real (test-mode) checkout."]
    )
    return _envelope(
        "\n".join(lines), intent="action", agents=[_AGENT_LABELS["logistics"]],
        ctx_summary=ctx_summary, warnings=warnings + extra_warn,
        suggested=["Add my next tournament to the calendar", "What should I pack?"],
        options=options,
    )


# ── formatting (wellness-safe / approval-gated language) ────────────────────

def _format_recovery(v: dict) -> str:
    parts = ", ".join(v.get("body_parts") or []) or "your body"
    out = (
        f"🩺 Recovery read — risk: {v.get('risk_level', 'unknown')} ({parts})\n"
        f"{v.get('summary', '')}\n"
        f"👉 Suggested adjustment: {v.get('recommended_action', '')}"
    )
    if v.get("pattern_type", "none") not in ("none", ""):
        out += f"\n🔎 Pattern — {v['pattern_type'].replace('_', ' ')}: {v.get('pattern_summary', '')}"
        if v.get("chain_message"):
            out += f"\n➡️ {v['chain_message']}"
    out += (
        "\n\n_This is wellness and self-management guidance, not a medical diagnosis. "
        "For persistent or worsening pain, please see a qualified professional._"
    )
    return out


def _format_performance(v: dict) -> str:
    return (
        f"📈 Performance ({v.get('trend', 'unknown')}): {v.get('summary', '')}\n"
        f"💪 Strongest: {v.get('strongest_area', '—')}   🎯 Work on: {v.get('weakest_area', '—')}\n"
        f"👉 Focus: {v.get('recommended_focus', '')}"
    )


def _format_sponsorship(v: dict) -> str:
    try:
        fit = f"{float(v.get('fit_score', 0)):.2f}"
    except (TypeError, ValueError):
        fit = str(v.get("fit_score", 0))
    return (
        f"🤝 Sponsor fit: {v.get('brand_name', '')} ({v.get('category', '')}, fit {fit})\n"
        f"Why: {v.get('reason', '')}\n\n"
        f"✉️ Draft outreach (review and edit before sending — nothing is sent automatically):\n"
        f"{v.get('draft_email', '')}"
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
