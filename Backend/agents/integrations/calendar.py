"""Calendar integration — persists an event so the dashboard shows it, and
inserts into Google Calendar when OAuth creds are configured.

The dashboard reads calendar_events from the backend, so the backend is always
the source of truth. Real Google Calendar insertion is a best-effort extra: if
GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN aren't set (or
the client libs aren't installed, or the call errors), we skip it silently and
still persist the event — so the demo works with zero Google setup.

Get the three Google values: create an OAuth client (Google Cloud Console →
Calendar API enabled → OAuth client ID), then mint a refresh token via the
OAuth Playground with scope https://www.googleapis.com/auth/calendar.events.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, timedelta

from agents.common import backend_client as backend

log = logging.getLogger("calendar")

_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
_DEFAULT_DAYS_OUT = 14  # if a tournament has no date, assume ~two weeks out


def _normalize_dates(start: str, end: str) -> tuple[str, str]:
    """Return (start, end) as all-day ISO dates; Google's all-day end is
    exclusive, so end is at least start + 1 day."""
    def parse(s: str):
        try:
            return date.fromisoformat((s or "")[:10])
        except ValueError:
            return None

    s = parse(start) or (date.today() + timedelta(days=_DEFAULT_DAYS_OUT))
    e = parse(end) or (s + timedelta(days=1))
    if e <= s:
        e = s + timedelta(days=1)
    return s.isoformat(), e.isoformat()


def _google_insert_sync(title: str, start: str, end: str, location: str) -> str:
    """Insert an all-day event into the user's primary calendar. Returns the
    event's htmlLink. Raises on failure (caller handles)."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=_SCOPES,
    )
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    body = {
        "summary": title,
        "location": location,
        "start": {"date": start},
        "end": {"date": end},
    }
    created = service.events().insert(calendarId="primary", body=body).execute()
    return created.get("htmlLink", "")


async def _maybe_google_insert(title, start, end, location) -> tuple[bool, str]:
    """Best-effort Google Calendar insert. Returns (inserted, html_link)."""
    if not (
        os.environ.get("GOOGLE_CLIENT_ID")
        and os.environ.get("GOOGLE_CLIENT_SECRET")
        and os.environ.get("GOOGLE_REFRESH_TOKEN")
    ):
        return False, ""
    try:
        link = await asyncio.to_thread(_google_insert_sync, title, start, end, location)
        log.info("Inserted '%s' into Google Calendar", title)
        return True, link
    except Exception as e:  # noqa: BLE001 - never block on Google
        log.warning("Google Calendar insert failed (persisted to backend anyway): %s", e)
        return False, ""


async def add_event(user_id: str, title: str, start: str, end: str,
                    location: str = "", event_type: str = "tournament") -> dict:
    """Persist a calendar event (dashboard source of truth) + optional GCal."""
    start, end = _normalize_dates(start, end)
    synced, link = await _maybe_google_insert(title, start, end, location)
    event = {
        "title": title, "event_type": event_type,
        "start_time": start, "end_time": end,
        "location": location, "source": "google_calendar" if synced else "agent",
        "metadata": {"google_link": link} if link else {},
    }
    event_id = await backend.create_calendar_event(user_id, event)
    return {"event_id": event_id, "synced_to_google": synced, "google_link": link, **event}
