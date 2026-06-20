"""Claude reasoning used inside the agents (Anthropic prize).

Two jobs:
  - classify(): split a raw journal dump into sectioned entries
                (Librarian, cheap/fast model).
  - assess_overtraining(): read recent injury/fitness history and decide
                whether there's an overtraining pattern (Recovery, stronger
                model).

Both use structured outputs (`output_config.format`) so the model returns
schema-valid JSON we can trust — no fragile prose parsing, no prefill.
Blocking SDK calls are pushed to a thread so they don't stall the agent's
asyncio event loop.
"""

from __future__ import annotations

import asyncio
import json

import anthropic

from . import config

# Lazily constructed so importing this module never requires a key.
_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        config.require_anthropic_key()  # raises a clear error if missing
        _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    return _client


_CLASSIFY_SYSTEM = (
    "You are the Librarian for an individual-sport athlete's performance "
    "journal. Split the athlete's raw dump (voice transcript, text, or "
    "transcribed notebook page) into discrete journal entries. Each entry is "
    "one coherent thought filed under exactly one section. Preserve the "
    "athlete's meaning; lightly clean filler words. Do not invent content."
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
    resp = _get_client().messages.create(
        model=config.CLASSIFY_MODEL,
        max_tokens=2048,
        system=_CLASSIFY_SYSTEM,
        output_config={
            "format": {"type": "json_schema", "schema": _CLASSIFY_SCHEMA}
        },
        messages=[{"role": "user", "content": dump}],
    )
    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    entries = json.loads(text).get("entries", [])
    # Defensive: keep only entries with a valid section and non-empty text.
    return [
        e for e in entries
        if e.get("section") in config.SECTIONS and e.get("text")
    ]


async def classify(dump: str) -> list[dict]:
    """Split a raw dump into [{section, text}] entries."""
    return await asyncio.to_thread(_classify_sync, dump)


_RECOVERY_SYSTEM = (
    "You are the Recovery agent for an endurance/individual-sport athlete. "
    "Given the newest injury/fitness note plus the athlete's recent history "
    "and metrics, decide whether there is an OVERTRAINING or injury-risk "
    "pattern. Treat as risk: the same body part reported sore/painful across "
    "3+ recent sessions, a sharp spike in training volume, or a declining "
    "recovery/readiness score alongside complaints. Be conservative — only "
    "flag a real, evidence-backed pattern, and cite what you saw."
)

_RECOVERY_SCHEMA = {
    "type": "object",
    "properties": {
        "overtraining_risk": {"type": "boolean"},
        "severity": {"type": "string", "enum": ["none", "low", "moderate", "high"]},
        "body_parts": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"},
        "recommendation": {"type": "string"},
    },
    "required": [
        "overtraining_risk",
        "severity",
        "body_parts",
        "rationale",
        "recommendation",
    ],
    "additionalProperties": False,
}


def _assess_overtraining_sync(
    new_entry: str, recent_injury: list[dict], recent_metrics: list[dict]
) -> dict:
    context = {
        "new_entry": new_entry,
        "recent_injury_log": recent_injury,
        "recent_metrics": recent_metrics,
    }
    resp = _get_client().messages.create(
        model=config.SYNTHESIS_MODEL,
        max_tokens=1024,
        system=_RECOVERY_SYSTEM,
        output_config={
            "format": {"type": "json_schema", "schema": _RECOVERY_SCHEMA}
        },
        messages=[
            {
                "role": "user",
                "content": (
                    "Assess overtraining/injury risk from this data:\n"
                    + json.dumps(context, indent=2)
                ),
            }
        ],
    )
    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    return json.loads(text)


async def assess_overtraining(
    new_entry: str,
    recent_injury: list[dict],
    recent_metrics: list[dict],
) -> dict:
    """Return an overtraining assessment dict (see _RECOVERY_SCHEMA)."""
    return await asyncio.to_thread(
        _assess_overtraining_sync, new_entry, recent_injury, recent_metrics
    )
