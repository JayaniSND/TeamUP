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


# ── Librarian: classify ────────────────────────────────────────────
_CLASSIFY_SYSTEM = (
    "You are the Librarian for an individual athlete's self-building sports "
    "analytics dashboard. Split the athlete's raw input (voice transcript, "
    "typed note, or transcribed notebook page) into discrete entries. Each "
    "entry is one coherent thought filed under exactly one section. Preserve "
    "meaning; lightly clean filler words; do not invent content."
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


# ── Recovery: overtraining / wellness ──────────────────────────────
_RECOVERY_SYSTEM = (
    "You are the Recovery agent for an individual athlete. Given the newest "
    "recovery/training note plus recent history and metrics, decide whether "
    "there is an overtraining or injury-risk pattern (same body part sore 3+ "
    "sessions, a training-volume spike, or a declining recovery score with "
    "complaints). Be conservative and cite what you saw. This is wellness and "
    "self-management guidance, NOT medical diagnosis."
)

_RECOVERY_SCHEMA = {
    "type": "object",
    "properties": {
        "risk_level": {"type": "string", "enum": ["none", "low", "medium", "high"]},
        "severity": {"type": "string", "enum": ["none", "low", "moderate", "high"]},
        "body_parts": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
        "recommended_action": {"type": "string"},
    },
    "required": ["risk_level", "severity", "body_parts", "summary", "recommended_action"],
    "additionalProperties": False,
}


def _assess_recovery_sync(note, recovery_logs, training, metrics) -> dict:
    ctx = {
        "new_note": note,
        "recent_recovery": recovery_logs,
        "recent_training": training,
        "recent_metrics": metrics,
    }
    return _structured(
        config.SYNTHESIS_MODEL,
        _RECOVERY_SYSTEM,
        "Assess recovery/overtraining risk from this data:\n" + json.dumps(ctx, indent=2),
        _RECOVERY_SCHEMA,
        1024,
    )


async def assess_recovery(note, recovery_logs, training, metrics) -> dict:
    return await asyncio.to_thread(
        _assess_recovery_sync, note, recovery_logs, training, metrics
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
