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

import logging

from database import supabase

log = logging.getLogger("athlete_context")

# Calendar event types that count as travel/away commitments.
_TRAVEL_EVENT_TYPES = {"tournament", "match", "travel", "competition", "away"}


def _select(table: str, user_id: str, limit: int, section: str | None = None) -> list[dict]:
    """Newest-first rows for a user; empty list on any failure (missing table,
    connection error). Never raises — callers can always rely on a list."""
    try:
        q = supabase.table(table).select("*").eq("user_id", user_id)
        if section:
            q = q.eq("section", section)
        try:
            res = q.order("created_at", desc=True).limit(limit).execute()
        except Exception:  # table may not have created_at — fall back unordered
            res = q.limit(limit).execute()
        return res.data or []
    except Exception as e:  # noqa: BLE001 — missing table / network / auth
        log.warning("read %s for %s failed: %s", table, user_id, e)
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
    try:
        res = supabase.table("athlete_profiles").select("*").eq("user_id", user_id).limit(1).execute()
        if res.data:
            row = dict(res.data[0])
            row["data_status"] = "ok"
            return row
    except Exception as e:  # noqa: BLE001 — table likely doesn't exist yet
        log.info("athlete_profiles table unavailable (%s); using placeholder profile", e)

    # No profile table / no row — return an honest placeholder. Downstream
    # prompts treat unknown fields as unknown rather than inventing details.
    return {
        "user_id": user_id,
        "name": None,
        "sport": None,
        "position": None,
        "level": None,
        "location": None,
        "goals": [],
        "data_status": "no_profile_table",  # see TODO(schema) above
    }


# ── bundled context + summary (what the orchestrator loads per request) ─────

def load_athlete_context(user_id: str) -> dict:
    """One real snapshot of the athlete from Supabase. Each value is independent
    so a single empty/missing table never blanks the whole context."""
    return {
        "user_id": user_id,
        "profile": get_athlete_profile(user_id),
        "entries": get_athlete_notes(user_id, limit=60),
        "recovery_logs": get_athlete_recovery_logs(user_id),
        "training": get_athlete_training_logs(user_id),
        "matches": get_athlete_match_results(user_id),
        "metrics": get_athlete_performance_metrics(user_id),
        "schedule": get_athlete_schedule(user_id),
        "travel": get_athlete_travel_context(user_id),
    }


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
    summary = ", ".join(f"{k}: {v}" for k, v in counts.items())

    warnings: list[str] = []
    if (ctx.get("profile") or {}).get("data_status") == "no_profile_table":
        warnings.append("No athlete profile on record yet (profile table not set up).")
    empty = [k for k, v in counts.items() if v == 0]
    if empty:
        warnings.append("No data yet for: " + ", ".join(empty) + ".")
    if all(v == 0 for v in counts.values()):
        warnings.append(
            "This athlete has no stored data — answers will be limited. "
            "Seed demo data with POST /admin/seed."
        )
    return summary, warnings
