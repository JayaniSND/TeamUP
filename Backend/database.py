"""Supabase client — single source of truth for DB access.

Reads connection details from the environment (never hard-coded). URL from
NEXT_PUBLIC_SUPABASE_URL (or SUPABASE_URL); key resolved in this order:

    SUPABASE_SERVICE_ROLE_KEY  ─┐  server-side secret — RECOMMENDED for this
    SUPABASE_SERVICE_KEY        │  backend. Bypasses Row Level Security so the
                                │  API can read/write all rows.
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY  the publishable/anon key — RLS-gated;
                                          if RLS is on with no policy for it,
                                          every query returns 0 rows silently.

This is a *server-side* backend: the browser never talks to Supabase directly
(it goes through this FastAPI service), so the service-role key is never shipped
to the frontend and using it here is safe. Keep it only in Backend/.env.
"""

import os

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = (
    os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "").strip()
    or os.environ.get("SUPABASE_URL", "").strip()
)

# Prefer a service-role key (bypasses RLS, server-only); fall back to publishable.
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    or os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    or os.environ.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", "").strip()
)
# Which kind of key is in use (for logging / diagnostics — never prints the key).
KEY_KIND = (
    "service_role"
    if (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY"))
    else "publishable/anon"
)

# Fail fast with an actionable message instead of a raw KeyError on import.
if not SUPABASE_URL or not SUPABASE_KEY:
    missing = []
    if not SUPABASE_URL:
        missing.append("NEXT_PUBLIC_SUPABASE_URL (or SUPABASE_URL)")
    if not SUPABASE_KEY:
        missing.append("SUPABASE_SERVICE_ROLE_KEY (or NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY)")
    raise RuntimeError(
        "Supabase is not configured. Missing environment variable(s): "
        f"{', '.join(missing)}. Copy Backend/.env.example to Backend/.env and fill "
        "them in (Project Settings → API in the Supabase dashboard)."
    )

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def test_connection() -> bool:
    try:
        res = supabase.table("entries").select("id", count="exact").limit(1).execute()
        print(f"✓ Connected to Supabase ({KEY_KIND} key) — entries visible: {res.count}")
        if not res.count and KEY_KIND != "service_role":
            print("  ⚠ 0 rows visible. If the table has data, RLS is likely blocking the "
                  "publishable key — add SUPABASE_SERVICE_ROLE_KEY to .env, or add an RLS policy.")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"✗ Connection failed: {e}")
        return False


if __name__ == "__main__":
    test_connection()
