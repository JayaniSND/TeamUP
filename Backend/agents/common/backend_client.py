"""Thin async client for the data backend's FastAPI (the data spine).

Every call degrades gracefully: if the backend is down it logs and returns an
empty list / None rather than crashing the agent. Point BACKEND_URL at the
bundled mock backend to run the whole chain before the real backend exists.
"""

from __future__ import annotations

import logging

import httpx

from . import config

log = logging.getLogger("backend_client")
_TIMEOUT = httpx.Timeout(10.0)


async def _get(path: str, params: dict):
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.get(f"{config.BACKEND_URL}{path}", params=params)
            r.raise_for_status()
            return r.json()
    except Exception as e:  # noqa: BLE001
        log.warning("GET %s failed: %s", path, e)
        return None


async def _post(path: str, payload: dict):
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.post(f"{config.BACKEND_URL}{path}", json=payload)
            r.raise_for_status()
            return r.json()
    except Exception as e:  # noqa: BLE001
        log.warning("POST %s failed: %s", path, e)
        return None


# ── writes ─────────────────────────────────────────────────────────
async def create_entry(user_id, section, text, meta=None):
    res = await _post("/entries", {"user_id": user_id, "section": section, "text": text, "meta": meta or {}})
    return (res or {}).get("entry_id")


async def create_agent_output(user_id, agent_name, section, summary,
                              severity="info", recommended_action="", related_entry_ids=None):
    res = await _post("/agent_outputs", {
        "user_id": user_id,
        "agent_name": agent_name,
        "section": section,
        "summary": summary,
        "severity": severity,
        "recommended_action": recommended_action,
        "related_entry_ids": related_entry_ids or [],
    })
    return (res or {}).get("output_id")


async def create_sponsorship_opportunity(user_id, opp: dict):
    res = await _post("/sponsorship_opportunities", {"user_id": user_id, **opp})
    return (res or {}).get("opportunity_id")


async def create_calendar_event(user_id, event: dict):
    res = await _post("/calendar/add", {"user_id": user_id, **event})
    return (res or {}).get("event_id")


# ── reads ──────────────────────────────────────────────────────────
async def recent_entries(user_id, section=None, limit=10) -> list[dict]:
    params = {"user_id": user_id, "limit": limit}
    if section:
        params["section"] = section
    return await _get("/entries", params) or []


async def recent_metrics(user_id, limit=20) -> list[dict]:
    return await _get("/metrics", {"user_id": user_id, "limit": limit}) or []


async def recent_match_results(user_id, limit=10) -> list[dict]:
    return await _get("/match_results", {"user_id": user_id, "limit": limit}) or []


async def recent_training(user_id, limit=10) -> list[dict]:
    return await _get("/training_sessions", {"user_id": user_id, "limit": limit}) or []


async def recent_recovery_logs(user_id, limit=10) -> list[dict]:
    return await _get("/recovery_logs", {"user_id": user_id, "limit": limit}) or []


async def athlete_profile(user_id) -> dict:
    return await _get("/athlete_profile", {"user_id": user_id}) or {}


async def recent_agent_outputs(user_id, section=None, limit=10) -> list[dict]:
    rows = await _get("/agent_outputs", {"user_id": user_id, "limit": limit}) or []
    return [r for r in rows if not section or r.get("section") == section]


async def chat(user_id, question) -> dict:
    """Ask the backend's RAG /chat endpoint (Coaching/Chat agent). Returns
    {answer, sources} or {} if unreachable."""
    return await _post("/chat", {"user_id": user_id, "question": question}) or {}
