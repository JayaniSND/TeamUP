"""Claude reasoning used inside the agents (Anthropic prize).

  - classify()           Librarian: split a raw dump into sectioned entries.
  - assess_recovery()    Recovery: fatigue/soreness/overtraining risk.
  - analyze_performance() Performance: win/loss + skill trends.
  - suggest_sponsorship() Sponsorship: brand fit + draft cold email.

All use structured outputs (`output_config.format`) so the model returns
schema-valid JSON — no fragile prose parsing, no prefill. Blocking SDK calls
run in a thread so they don't stall the agent's asyncio event loop.
"""

from __future__ import annotations

import asyncio
import json

import anthropic

from . import config

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        config.require_anthropic_key()
        _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    return _client


def _structured(model: str, system: str, user: str, schema: dict, max_tokens: int) -> dict:
    resp = _get_client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": user}],
    )
    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    return json.loads(text)


# ── Gateway intent router (ASI:One front door) ─────────────────────
# Framework v4 §6a: one chat interface, Claude reads intent and routes.
#   log    → it's a journal dump to file (Librarian)
#   ask    → an open-ended history/pattern question → RAG over /chat
#   action → a domain request handled by a specific specialist agent
_INTENT_SYSTEM = (
    "You route an individual athlete's chat message to the right handler in a "
    "sports-analytics assistant. Choose ONE intent:\n"
    "• 'log' — the athlete is recording what happened (practice/match/how they "
    "feel). e.g. 'just finished practice, serve felt sharp, knee sore again'.\n"
    "• 'ask' — an open-ended history/pattern question best answered by searching "
    "across their journal. e.g. 'how has my serve been trending', 'what patterns "
    "do you see in my losses', 'what should I focus on next week'. Set agent=none.\n"
    "• 'action' — a request a specific specialist owns. Set agent to:\n"
    "    recovery    — body/fatigue/overtraining ('am I overtrained', 'how's my body')\n"
    "    performance — win/loss or form summaries ('how am I performing')\n"
    "    sponsorship — sponsor fit or outreach drafting ('find sponsors', 'draft outreach')\n"
    "    logistics   — tournaments/travel/calendar ('find a tournament', 'add to calendar')\n"
    "When unsure between 'ask' and 'action', prefer 'ask'. Only use 'log' when the "
    "athlete is clearly reporting events, not asking a question."
)

_INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": ["log", "ask", "action"]},
        "agent": {
            "type": "string",
            "enum": ["recovery", "performance", "sponsorship", "logistics", "none"],
        },
    },
    "required": ["intent", "agent"],
    "additionalProperties": False,
}


def _classify_intent_sync(message: str) -> dict:
    return _structured(config.CLASSIFY_MODEL, _INTENT_SYSTEM, message, _INTENT_SCHEMA, 256)


async def classify_intent(message: str) -> dict:
    """Return {'intent': log|ask|action, 'agent': recovery|...|none}."""
    return await asyncio.to_thread(_classify_intent_sync, message)


# ── Librarian: classify ────────────────────────────────────────────
_CLASSIFY_SYSTEM = (
    "You are the Librarian for an individual athlete's self-building sports "
    "analytics dashboard. Split the athlete's raw input (voice transcript, "
    "typed note, or transcribed notebook page) into discrete entries. Each "
    "entry is one coherent thought filed under exactly one section. Preserve "
    "meaning; lightly clean filler words; do not invent content.\n"
    "Section guidance: file any mention of a specific tournament, competition, "
    "match to attend, travel, or scheduling under `logistics` — even when the "
    "athlete phrases it as wanting to enter/sign up. Use `goals` ONLY for "
    "aspirational targets (e.g. 'win a regional title', 'get my serve above 90 "
    "mph'), not concrete events to put on a calendar."
)

_CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "entries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section": {"type": "string", "enum": config.SECTIONS},
                    "text": {"type": "string"},
                },
                "required": ["section", "text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["entries"],
    "additionalProperties": False,
}


def _classify_sync(dump: str) -> list[dict]:
    data = _structured(config.CLASSIFY_MODEL, _CLASSIFY_SYSTEM, dump, _CLASSIFY_SCHEMA, 2048)
    return [
        e for e in data.get("entries", [])
        if e.get("section") in config.SECTIONS and e.get("text")
    ]


async def classify(dump: str) -> list[dict]:
    """Split a raw dump into [{section, text}] entries."""
    return await asyncio.to_thread(_classify_sync, dump)


# ── Recovery: overtraining / wellness (passive linguistic-drift) ───
# Framework v4 §6.2: don't just keyword-match injuries — read ~14 days of
# entries across ALL sections for linguistic drift (serve "explosive" →
# "muscling through", a body side described with rising negativity, load
# spikes with no rest language), even before the athlete mentions pain.
_RECOVERY_SYSTEM = (
    "You are the Recovery & Pattern agent for an individual athlete, reading like "
    "a sports physiologist AND a performance psychologist. You are given the "
    "athlete's recent journal entries across ALL sections (up to ~60 days), plus "
    "structured recovery logs, training, and metrics. Produce TWO findings:\n\n"
    "1) PHYSICAL (shorter ~14-day horizon): an overtraining/injury-risk read, "
    "including subtle LINGUISTIC DRIFT — not just injury keywords. Flag e.g. the "
    "same skill described with falling energy over time ('explosive' → 'muscling "
    "through'), a body part referenced with rising negativity, or a load spike "
    "with no rest language — even before the word 'pain' appears. Also the classic "
    "signals: same body part sore 3+ sessions, volume spike, declining recovery "
    "score with complaints.\n\n"
    "2) BEHAVIORAL/EMOTIONAL ARC (longer 30-60 day horizon): patterns that only "
    "show across timestamps, not in one entry. Classify pattern_type as one of: "
    "confidence_rising (language/wins/mood trending up), burnout_arc ('why am I "
    "even playing' followed later by strong entries), momentum_dip (3+ losses, "
    "falling energy, shorter sessions), readiness_window (low fatigue + positive "
    "mood + strong training in one window), plateau (metrics flat 4+ weeks despite "
    "training), or none. When a positive arc is detected (confidence_rising or "
    "readiness_window), set chain_to='logistics' with a chain_message inviting the "
    "athlete to enter an upcoming tournament. For momentum_dip use chain_to="
    "'performance'; for plateau use chain_to='coaching'; otherwise chain_to='none'.\n\n"
    "Be conservative, quote what you actually saw, and only chain on a real arc. "
    "This is wellness and self-management guidance, NOT medical diagnosis."
)

_RECOVERY_SCHEMA = {
    "type": "object",
    "properties": {
        "risk_level": {"type": "string", "enum": ["none", "low", "medium", "high"]},
        "severity": {"type": "string", "enum": ["none", "low", "moderate", "high"]},
        "body_parts": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
        "recommended_action": {"type": "string"},
        "pattern_type": {
            "type": "string",
            "enum": [
                "none", "confidence_rising", "burnout_arc",
                "momentum_dip", "readiness_window", "plateau",
            ],
        },
        "pattern_summary": {"type": "string"},
        "chain_to": {
            "type": "string",
            "enum": ["none", "logistics", "performance", "coaching"],
        },
        "chain_message": {"type": "string"},
    },
    "required": [
        "risk_level", "severity", "body_parts", "summary", "recommended_action",
        "pattern_type", "pattern_summary", "chain_to", "chain_message",
    ],
    "additionalProperties": False,
}


def _assess_recovery_sync(note, recent_entries, recovery_logs, training, metrics) -> dict:
    ctx = {
        "new_note": note,
        "recent_entries_14d": recent_entries,
        "recent_recovery_logs": recovery_logs,
        "recent_training": training,
        "recent_metrics": metrics,
    }
    return _structured(
        config.SYNTHESIS_MODEL,
        _RECOVERY_SYSTEM,
        "Assess recovery/overtraining risk (including linguistic drift) from this "
        "data:\n" + json.dumps(ctx, indent=2),
        _RECOVERY_SCHEMA,
        1024,
    )


async def assess_recovery(note, recent_entries, recovery_logs, training, metrics) -> dict:
    return await asyncio.to_thread(
        _assess_recovery_sync, note, recent_entries, recovery_logs, training, metrics
    )


# ── Performance: trends ────────────────────────────────────────────
_PERF_SYSTEM = (
    "You are the Performance agent for an individual athlete. From recent "
    "match results, training sessions, and metrics, summarize the athlete's "
    "form: win/loss trend, strongest and weakest area, and one concrete "
    "improvement focus. Ground every claim in the supplied data."
)

_PERF_SCHEMA = {
    "type": "object",
    "properties": {
        "trend": {"type": "string", "enum": ["improving", "steady", "declining", "unknown"]},
        "summary": {"type": "string"},
        "strongest_area": {"type": "string"},
        "weakest_area": {"type": "string"},
        "recommended_focus": {"type": "string"},
    },
    "required": ["trend", "summary", "strongest_area", "weakest_area", "recommended_focus"],
    "additionalProperties": False,
}


def _analyze_performance_sync(note, matches, training, metrics) -> dict:
    ctx = {
        "new_note": note,
        "recent_match_results": matches,
        "recent_training": training,
        "recent_metrics": metrics,
    }
    return _structured(
        config.SYNTHESIS_MODEL,
        _PERF_SYSTEM,
        "Summarize performance from this data:\n" + json.dumps(ctx, indent=2),
        _PERF_SCHEMA,
        1024,
    )


async def analyze_performance(note, matches, training, metrics) -> dict:
    return await asyncio.to_thread(
        _analyze_performance_sync, note, matches, training, metrics
    )


# ── Sponsorship: brand fit + draft email (approval-gated) ──────────
_SPONSOR_SYSTEM = (
    "You are the Sponsorship agent for an individual athlete. From the "
    "athlete's profile, recent results, metrics, and media notes, propose ONE "
    "realistic sponsor fit and draft a short, professional cold outreach "
    "email the athlete can review and edit. Never claim the email was sent — "
    "this is a draft for human approval. Keep the email under 150 words."
)

_SPONSOR_SCHEMA = {
    "type": "object",
    "properties": {
        "brand_name": {"type": "string"},
        "category": {"type": "string"},
        "fit_score": {"type": "number"},
        "reason": {"type": "string"},
        "draft_email": {"type": "string"},
    },
    "required": ["brand_name", "category", "fit_score", "reason", "draft_email"],
    "additionalProperties": False,
}


def _suggest_sponsorship_sync(note, profile, matches, metrics, media) -> dict:
    ctx = {
        "new_note": note,
        "athlete_profile": profile,
        "recent_match_results": matches,
        "recent_metrics": metrics,
        "media_notes": media,
    }
    return _structured(
        config.SYNTHESIS_MODEL,
        _SPONSOR_SYSTEM,
        "Suggest a sponsor fit and draft outreach from this data:\n"
        + json.dumps(ctx, indent=2),
        _SPONSOR_SCHEMA,
        1024,
    )


async def suggest_sponsorship(note, profile, matches, metrics, media) -> dict:
    return await asyncio.to_thread(
        _suggest_sponsorship_sync, note, profile, matches, metrics, media
    )


# ── Logistics: extract a tournament from scraped/cached page text ──
_TOURNEY_SYSTEM = (
    "You are the Logistics agent for an individual athlete. From the raw web "
    "page text of a tournament finder (and the athlete's note), extract the ONE "
    "most relevant upcoming tournament near the requested location/date window. "
    "Return clean structured fields. If the text has no real event, set name to "
    "'' and explain in summary."
)

_TOURNEY_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "location": {"type": "string"},
        "start_date": {"type": "string"},   # ISO date if known, else ''
        "end_date": {"type": "string"},
        "venue": {"type": "string"},
        "url": {"type": "string"},
        "summary": {"type": "string"},
    },
    "required": ["name", "location", "start_date", "end_date", "venue", "url", "summary"],
    "additionalProperties": False,
}


def _extract_tournament_sync(note, page_text) -> dict:
    ctx = {"athlete_note": note, "page_text": page_text}
    return _structured(
        config.SYNTHESIS_MODEL,
        _TOURNEY_SYSTEM,
        "Extract the best-matching tournament:\n" + json.dumps(ctx, indent=2),
        _TOURNEY_SCHEMA,
        800,
    )


async def extract_tournament(note, page_text) -> dict:
    return await asyncio.to_thread(_extract_tournament_sync, note, page_text)


# ── Scout: summarize an opponent from scraped/cached page text ─────
_SCOUT_SYSTEM = (
    "You are the Scout agent for an individual athlete. From the raw web page "
    "text of an opponent's recent results/profile (and the athlete's note), "
    "summarize the opponent's playing patterns, strengths, weaknesses, and ONE "
    "concrete tactical recommendation the athlete can use. Ground claims in the "
    "text; if information is thin, say so."
)

_SCOUT_SCHEMA = {
    "type": "object",
    "properties": {
        "opponent": {"type": "string"},
        "patterns": {"type": "string"},
        "strengths": {"type": "string"},
        "weaknesses": {"type": "string"},
        "tactical_recommendation": {"type": "string"},
    },
    "required": ["opponent", "patterns", "strengths", "weaknesses", "tactical_recommendation"],
    "additionalProperties": False,
}


def _scout_opponent_sync(note, page_text) -> dict:
    ctx = {"athlete_note": note, "page_text": page_text}
    return _structured(
        config.SYNTHESIS_MODEL,
        _SCOUT_SYSTEM,
        "Summarize the opponent and give a tactical edge:\n" + json.dumps(ctx, indent=2),
        _SCOUT_SCHEMA,
        900,
    )


async def scout_opponent(note, page_text) -> dict:
    return await asyncio.to_thread(_scout_opponent_sync, note, page_text)
