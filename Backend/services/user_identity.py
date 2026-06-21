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
    # The canonical backend id is a real UUID, configured via USER_ID or
    # DEFAULT_USER_ID. Never let the fallback be the alias itself — otherwise
    # 'demo-athlete' resolves right back to 'demo-athlete' and misses all the
    # UUID-keyed data. Pick the first configured id that ISN'T the alias.
    fallback = next(
        (
            v
            for v in (
                os.environ.get("USER_ID", "").strip(),
                os.environ.get("DEFAULT_USER_ID", "").strip(),
            )
            if v and v != DEMO_ALIAS
        ),
        DEMO_ALIAS,
    )
    if not requested or requested == DEMO_ALIAS:
        return fallback
    return requested
