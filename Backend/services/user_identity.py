"""User identity helpers for backend-owned data access.

The frontend may send the human-friendly demo alias `demo-athlete`, but the
Supabase MVP schema uses UUID user ids. Resolve that alias at the API boundary
so every agent/RAG/database path queries the same backend-owned id.
"""

from __future__ import annotations

import os


DEMO_ALIAS = "demo-athlete"


def resolve_user_id(user_id: str | None) -> str:
    requested = (user_id or "").strip()
    fallback = (
        os.environ.get("DEFAULT_USER_ID", "").strip()
        or os.environ.get("USER_ID", "").strip()
        or DEMO_ALIAS
    )
    if not requested or requested == DEMO_ALIAS:
        return fallback
    return requested
