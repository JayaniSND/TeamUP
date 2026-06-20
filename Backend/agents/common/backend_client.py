"""Thin async client for Dev 2's FastAPI (the data + RAG spine).

Every call is resilient: if the backend is down or returns an error we log
and degrade gracefully (return an empty list / None) rather than crashing
the agent. That keeps the agent demo-able even before Dev 2's service is up
— point BACKEND_URL at the bundled mock backend and it just works.

Endpoints used (from the locked API contract in the build plan):
  POST /entries          -> {entry_id}
  GET  /entries          -> [{entry_id, section, text, ts, meta}]
  GET  /progress         -> [{ts, value}]
  POST /recovery_flags   -> {flag_id}   (Recovery surfaces a flag here)
"""

from __future__ import annotations

import logging

import httpx

from . import config

log = logging.getLogger("backend_client")

_TIMEOUT = httpx.Timeout(10.0)


async def create_entry(user_id: str, section: str, text: str, meta: dict | None = None):
    """POST a single classified entry. Returns the created entry_id or None."""
    payload = {"user_id": user_id, "section": section, "text": text, "meta": meta or {}}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.post(f"{config.BACKEND_URL}/entries", json=payload)
            r.raise_for_status()
            return r.json().get("entry_id")
    except Exception as e:  # noqa: BLE001 - degrade gracefully
        log.warning("create_entry failed (%s): %s", config.BACKEND_URL, e)
        return None


async def recent_entries(user_id: str, section: str, limit: int = 10) -> list[dict]:
    """GET recent entries for a user, optionally filtered by section."""
    params = {"user_id": user_id, "section": section, "limit": limit}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.get(f"{config.BACKEND_URL}/entries", params=params)
            r.raise_for_status()
            return r.json()
    except Exception as e:  # noqa: BLE001
        log.warning("recent_entries failed: %s", e)
        return []


async def recent_metrics(user_id: str, limit: int = 20) -> list[dict]:
    """GET recent metric rows (volume, recovery score, etc.)."""
    params = {"user_id": user_id, "limit": limit}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.get(f"{config.BACKEND_URL}/metrics", params=params)
            r.raise_for_status()
            return r.json()
    except Exception as e:  # noqa: BLE001
        log.warning("recent_metrics failed: %s", e)
        return []


async def create_recovery_flag(user_id: str, assessment: dict):
    """POST a Recovery overtraining flag the dashboard surfaces."""
    payload = {"user_id": user_id, **assessment}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.post(f"{config.BACKEND_URL}/recovery_flags", json=payload)
            r.raise_for_status()
            return r.json().get("flag_id")
    except Exception as e:  # noqa: BLE001
        log.warning("create_recovery_flag failed: %s", e)
        return None
