"""Athlete data-access layer — clean, reusable, read-only Supabase queries.

Every function here reads REAL rows from Supabase for a single athlete. There
is no mock data: if a table is empty the function returns an empty list, and if
a table does not exist yet the query degrades gracefully (logs + empty result)
rather than crashing the request. The orchestrator uses these to ground every
answer in the athlete's actual stored data.

Tables used (created by main.py's docstring / POST /admin/seed):
    entries · training_sessions · match_results · recovery_logs · metrics
    calendar_events · sponsorship_opportunities · agent_outputs

TODO(schema): there is no dedicated athlete-profile table yet. `get_athlete_profile`
returns a clearly-marked placeholder when one is absent — see its docstring for
the suggested `athlete_profiles` schema. Do NOT hard-code a fake identity here.
"""

from __future__ import annotations

from copy import deepcopy
import logging
import os
import time

from database import supabase
from .user_identity import resolve_user_id

log = logging.getLogger("athlete_context")

# Calendar event types that count as travel/away commitments.
_TRAVEL_EVENT_TYPES = {"tournament", "match", "travel", "competition", "away"}
_CONTEXT_CACHE_TTL_SECONDS = float(os.environ.get("ATHLETE_CONTEXT_CACHE_TTL_SECONDS", "20"))
_context_cache: dict[tuple[str, str], tuple[float, dict]] = {}


def clear_context_cache(user_id: str | None = None) -> None:
    """Invalidate cached athlete snapshots after writes."""
    if user_id is None:
        _context_cache.clear()
        return
    resolved = resolve_user_id(user_id)
    for key in [key for key in _context_cache if key[0] == resolved]:
        _context_cache.pop(key, None)


def _select(table: str, user_id: str, limit: int, section: str | None = None) -> list[dict]:
    """Newest-first rows for a user; empty list on any failure (missing table,
    connection error). Never raises — callers can always rely on a list."""
    resolved_user_id = resolve_user_id(user_id)
    try:
        q = supabase.table(table).select("*").eq("user_id", resolved_user_id)
        if section:
            q = q.eq("section", section)
        try:
            res = q.order("created_at", desc=True).limit(limit).execute()
        except Exception:  # table may not have created_at — fall back unordered
            res = q.limit(limit).execute()
        return res.data or []
    except Exception as e:  # noqa: BLE001 — missing table / network / auth
        log.warning("read %s for %s failed: %s", table, resolved_user_id, e)
        return []


# ── individual reads (the public data-access API) ──────────────────────────

def get_athlete_training_logs(user_id: str, limit: int = 20) -> list[dict]:
    return _select("training_sessions", user_id, limit)


def get_athlete_recovery_logs(user_id: str, limit: int = 20) -> list[dict]:
    return _select("recovery_logs", user_id, limit)


def get_athlete_match_results(user_id: str, limit: int = 20) -> list[dict]:
    return _select("match_results", user_id, limit)


def get_athlete_performance_metrics(user_id: str, limit: int = 50) -> list[dict]:
    return _select("metrics", user_id, limit)


def get_athlete_schedule(user_id: str, limit: int = 20) -> list[dict]:
    """All calendar events for the athlete (newest-first)."""
    return _select("calendar_events", user_id, limit)


def get_athlete_notes(user_id: str, section: str | None = None, limit: int = 60) -> list[dict]:
    """Filed journal entries (voice/text/photo-converted), optionally by section."""
    return _select("entries", user_id, limit, section)


def get_athlete_travel_context(user_id: str) -> dict:
    """Travel-relevant slice of the calendar: away/tournament/match commitments
    plus the distinct destinations. Used by the Travel planner — it never
    fabricates flights/hotels, only reasons over these real commitments."""
    events = get_athlete_schedule(user_id, limit=40)
    trips = [e for e in events if (e.get("event_type") or "").lower() in _TRAVEL_EVENT_TYPES]
    destinations = sorted({e.get("location") for e in trips if e.get("location")})
    return {"trips": trips, "destinations": destinations}


def _travel_from_events(events: list[dict]) -> dict:
    trips = [e for e in events if (e.get("event_type") or "").lower() in _TRAVEL_EVENT_TYPES]
    destinations = sorted({e.get("location") for e in trips if e.get("location")})
    return {"trips": trips, "destinations": destinations}


def get_athlete_profile(user_id: str) -> dict:
    """Athlete profile from Supabase if a profile table exists, else a clearly
    marked placeholder (NOT a fabricated identity).

    TODO(schema): create an `athlete_profiles` table and remove the placeholder:
        create table if not exists athlete_profiles (
          user_id text primary key,
          name text, sport text, position text, level text, location text,
          dominant_side text, goals jsonb default '[]',
          strengths jsonb default '[]', weaknesses jsonb default '[]',
          injury_history jsonb default '[]', created_at timestamptz default now()
        );
    """
    resolved_user_id = resolve_user_id(user_id)
    try:
        res = supabase.table("athlete_profiles").select("*").eq("user_id", resolved_user_id).limit(1).execute()
        if res.data:
            row = dict(res.data[0])
            row["data_status"] = "ok"
            return row
    except Exception as e:  # noqa: BLE001 — table likely doesn't exist yet
        log.info("athlete_profiles table unavailable (%s); using placeholder profile", e)

    # No profile table / no row — return an honest placeholder. Downstream
    # prompts treat unknown fields as unknown rather than inventing details.
    return {
        "user_id": resolved_user_id,
        "name": None,
        "sport": None,
        "position": None,
        "level": None,
        "location": None,
        "goals": [],
        "data_status": "no_profile_table",  # see TODO(schema) above
    }


# ── bundled context + summary (what the orchestrator loads per request) ─────

def load_athlete_context(user_id: str, scope: str = "full") -> dict:
    """One real snapshot of the athlete from Supabase. Each value is independent
    so a single empty/missing table never blanks the whole context."""
    resolved_user_id = resolve_user_id(user_id)
    scope = scope if scope in {"performance", "recovery", "logistics", "light", "full"} else "full"
    cache_key = (resolved_user_id, scope)
    now = time.monotonic()
    cached = _context_cache.get(cache_key)
    if cached and now - cached[0] <= _CONTEXT_CACHE_TTL_SECONDS:
        return deepcopy(cached[1])

    snapshot = {"user_id": resolved_user_id, "profile": {}, "_scope": scope, "_loaded_sections": []}
    if scope == "performance":
        snapshot.update({
            "entries": [],
            "recovery_logs": [],
            "training": get_athlete_training_logs(resolved_user_id, limit=3),
            "matches": get_athlete_match_results(resolved_user_id, limit=3),
            "metrics": get_athlete_performance_metrics(resolved_user_id, limit=8),
            "schedule": [],
            "travel": {"trips": [], "destinations": []},
            "_loaded_sections": ["training", "matches", "metrics"],
        })
    elif scope == "recovery":
        snapshot.update({
            "entries": get_athlete_notes(resolved_user_id, section="recovery", limit=8),
            "recovery_logs": get_athlete_recovery_logs(resolved_user_id, limit=5),
            "training": get_athlete_training_logs(resolved_user_id, limit=5),
            "matches": [],
            "metrics": get_athlete_performance_metrics(resolved_user_id, limit=8),
            "schedule": [],
            "travel": {"trips": [], "destinations": []},
            "_loaded_sections": ["entries", "recovery_logs", "training", "metrics"],
        })
    elif scope == "logistics":
        schedule = get_athlete_schedule(resolved_user_id, limit=5)
        snapshot.update({
            "entries": [],
            "recovery_logs": [],
            "training": [],
            "matches": [],
            "metrics": [],
            "schedule": schedule,
            "travel": _travel_from_events(schedule),
            "_loaded_sections": ["schedule"],
        })
    else:
        schedule = get_athlete_schedule(resolved_user_id, limit=8)
        snapshot.update({
            "profile": get_athlete_profile(resolved_user_id),
            "entries": get_athlete_notes(resolved_user_id, limit=20),
            "recovery_logs": get_athlete_recovery_logs(resolved_user_id, limit=8),
            "training": get_athlete_training_logs(resolved_user_id, limit=8),
            "matches": get_athlete_match_results(resolved_user_id, limit=8),
            "metrics": get_athlete_performance_metrics(resolved_user_id, limit=16),
            "schedule": schedule,
            "travel": _travel_from_events(schedule),
            "_loaded_sections": ["entries", "recovery_logs", "training", "matches", "metrics", "schedule"],
        })
    _context_cache[cache_key] = (now, deepcopy(snapshot))
    return snapshot


def summarize_context(ctx: dict) -> tuple[str, list[str]]:
    """Human-readable one-liner of what real data was loaded, plus warnings for
    empty buckets — so the orchestrator can say what's missing instead of
    hallucinating around it."""
    counts = {
        "entries": len(ctx.get("entries") or []),
        "recovery_logs": len(ctx.get("recovery_logs") or []),
        "training": len(ctx.get("training") or []),
        "matches": len(ctx.get("matches") or []),
        "metrics": len(ctx.get("metrics") or []),
        "schedule": len(ctx.get("schedule") or []),
    }
    loaded = set(ctx.get("_loaded_sections") or counts.keys())
    summary = ", ".join(f"{k}: {v}" for k, v in counts.items() if k in loaded)

    warnings: list[str] = []
    if (ctx.get("profile") or {}).get("data_status") == "no_profile_table":
        warnings.append("No athlete profile on record yet (profile table not set up).")
    empty = [k for k, v in counts.items() if k in loaded and v == 0]
    if empty:
        warnings.append("No data yet for: " + ", ".join(empty) + ".")
    if all(v == 0 for v in counts.values()):
        warnings.append(
            "This athlete has no stored data — answers will be limited. "
            "Seed demo data with POST /admin/seed."
        )
    return summary, warnings
