"""calendar_client.py — Google Calendar integration for the Logistics agent.

One-time setup:
  1. console.cloud.google.com → APIs & Services → enable Google Calendar API
  2. Credentials → Create OAuth 2.0 Client ID → Desktop app → download JSON
     → save as  Backend/client_secrets.json  (already in .gitignore)
  3. Run once from the Backend/ directory to authorise:
         python -c "from agents.common import calendar_client; calendar_client._authorize()"
     A browser opens → sign in → token.json is written to Backend/.
  4. After that, create_event() works silently.

If credentials aren't configured, create_event() returns None — the
Logistics agent notes this in its reply and keeps going.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger("calendar_client")

_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
_BASE = Path(__file__).parent.parent.parent   # Backend/
_SECRETS_FILE = _BASE / "client_secrets.json"
_TOKEN_FILE = _BASE / "token.json"
_CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID", "primary")


def _authorize():
    """Interactive OAuth flow — call once from a terminal, not from agent code."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(str(_SECRETS_FILE), _SCOPES)
    creds = flow.run_local_server(port=0)
    _TOKEN_FILE.write_text(creds.to_json())
    print(f"[calendar] token saved to {_TOKEN_FILE}")
    return creds


def _get_credentials():
    if not _TOKEN_FILE.exists():
        return None
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), _SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _TOKEN_FILE.write_text(creds.to_json())
        return creds if creds.valid else None
    except Exception as e:
        log.warning("Could not load Google credentials: %s", e)
        return None


def create_event(
    summary: str,
    start_date: str,
    end_date: str,
    location: str = "",
    description: str = "",
) -> str | None:
    """Create an all-day event. Returns the HTML event link, or None on failure."""
    creds = _get_credentials()
    if creds is None:
        log.info("Google Calendar not configured — skipping event creation")
        return None
    try:
        from googleapiclient.discovery import build
        service = build("calendar", "v3", credentials=creds)
        event = service.events().insert(
            calendarId=_CALENDAR_ID,
            body={
                "summary": summary,
                "location": location,
                "description": description,
                "start": {"date": start_date},
                "end": {"date": end_date},
            },
        ).execute()
        return event.get("htmlLink")
    except Exception as e:
        log.warning("Google Calendar event creation failed: %s", e)
        return None
