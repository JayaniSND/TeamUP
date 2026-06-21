"""calendar_client.py — thin wrapper around the Google Calendar API.

Creates calendar events for trips/tournaments on an athlete's own Google
Calendar. Uses OAuth2 USER credentials, not a service account — writing to
a real person's personal calendar requires their explicit one-time
consent, which is what authorize_google_calendar.py captures.

⚠️ ACTION NEEDED FROM YOU before this works (one-time setup):
  1. In Google Cloud Console, create/select a project and enable the
     "Google Calendar API" for it.
  2. Configure the OAuth consent screen (External; while the app is in
     "Testing" mode, add the athlete's Google account as a test user —
     otherwise Google will refuse to let it log in).
  3. Create an OAuth 2.0 Client ID of type "Desktop app", download it,
     save it as google_credentials.json at the path
     GOOGLE_CALENDAR_CREDENTIALS_PATH points to (default below).
  4. Run `python -m agents.authorize_google_calendar` once, from Backend/.
     It opens a real browser, the athlete logs in and grants calendar
     access, and a refresh token gets saved to google_token.json.
  5. Add BOTH google_credentials.json and google_token.json to .gitignore.
     They are live credentials — committing them to your shared repo
     would leak access to a real person's real calendar.

After that one-time setup, this module works headlessly — no further
action needed from you.
"""

from __future__ import annotations

import logging
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

log = logging.getLogger("calendar_client")

# Minimal scope on purpose — event read/write only, not full calendar
# access (no calendar deletion, no settings changes, no other calendars).
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

CREDENTIALS_PATH = os.environ.get(
    "GOOGLE_CALENDAR_CREDENTIALS_PATH", "agents/common/google_credentials.json"
)
TOKEN_PATH = os.environ.get("GOOGLE_CALENDAR_TOKEN_PATH", "agents/common/google_token.json")


def _load_credentials() -> Credentials:
    if not os.path.isfile(TOKEN_PATH):
        raise RuntimeError(
            f"No Google Calendar token found at {TOKEN_PATH}. Run "
            "`python -m agents.authorize_google_calendar` once from Backend/ "
            "to authorize this app against the athlete's calendar — see this "
            "module's docstring for the full one-time setup."
        )
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return creds


def create_event(
    summary: str,
    start_date: str,
    end_date: str,
    location: str = "",
    description: str = "",
) -> str | None:
    """Create an all-day event on the athlete's primary calendar.

    start_date / end_date must be real 'YYYY-MM-DD' strings. Returns the
    event's htmlLink on success, or None on any failure — callers should
    degrade gracefully, same pattern as backend_client.py's HTTP calls.
    """
    try:
        creds = _load_credentials()
        service = build("calendar", "v3", credentials=creds)
        event = {
            "summary": summary,
            "location": location,
            "description": description,
            "start": {"date": start_date},
            "end": {"date": end_date},
        }
        created = service.events().insert(calendarId="primary", body=event).execute()
        return created.get("htmlLink")
    except Exception as e:  # noqa: BLE001 — degrade gracefully, don't crash the agent
        log.warning("create_event failed: %s", e)
        return None