"""Shared configuration for the agent layer.

Single source of truth for the section taxonomy, model ids, backend URL,
agent addresses, and the section->agent routing map. Everything reads from
the environment (.env) so the agents stay in sync without scattered values.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

# Load Backend/.env if present (CWD or parents).
load_dotenv()

# The section taxonomy. MUST match the data backend's `SECTIONS` and the frontend copy.
SECTIONS: list[str] = [
    "training",
    "performance",
    "match_results",
    "recovery",
    "coaching",
    "logistics",
    "sponsorship",
    "goals",
    "media_notes",
]

# The data backend's FastAPI. Defaults to the bundled mock backend.
BACKEND_URL: str = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")

# Athlete to attribute entries to when a dump doesn't carry one.
DEFAULT_USER_ID: str = os.environ.get("DEFAULT_USER_ID", "demo-athlete")

# ── Agent addresses (filled in after first boot — see README) ──────
LIBRARIAN_ADDRESS: str = os.environ.get("LIBRARIAN_ADDRESS", "").strip()
RECOVERY_ADDRESS: str = os.environ.get("RECOVERY_ADDRESS", "").strip()
PERFORMANCE_ADDRESS: str = os.environ.get("PERFORMANCE_ADDRESS", "").strip()
SPONSORSHIP_ADDRESS: str = os.environ.get("SPONSORSHIP_ADDRESS", "").strip()
LOGISTICS_ADDRESS: str = os.environ.get("LOGISTICS_ADDRESS", "").strip()  # external logistics agent


def address_for(agent_name: str) -> str:
    """Resolve a specialist agent name to its configured address ('' if unset).

    Read dynamically (module attributes) so run_local.py can patch addresses
    at runtime for in-process Bureau testing.
    """
    import agents.common.config as cfg  # self, for live attribute lookup

    return {
        "recovery": cfg.RECOVERY_ADDRESS,
        "performance": cfg.PERFORMANCE_ADDRESS,
        "sponsorship": cfg.SPONSORSHIP_ADDRESS,
        "logistics": cfg.LOGISTICS_ADDRESS,
    }.get(agent_name, "")


# Which specialist agents should react when a section appears in a dump.
# The Orchestrator triggers the union of these for the classified sections.
SECTION_AGENTS: dict[str, list[str]] = {
    "recovery": ["recovery"],
    "training": ["recovery", "performance"],
    "match_results": ["performance", "sponsorship"],
    "performance": ["performance"],
    "logistics": ["logistics"],
    "sponsorship": ["sponsorship"],
    "media_notes": ["sponsorship"],
    "goals": [],
    "coaching": [],
}

# ── Models ─────────────────────────────────────────────────────────
CLASSIFY_MODEL: str = os.environ.get("CLASSIFY_MODEL", "claude-haiku-4-5")
SYNTHESIS_MODEL: str = os.environ.get("SYNTHESIS_MODEL", "claude-sonnet-4-6")

# ── ASI:One bonus router ───────────────────────────────────────────
ASI_ONE_API_KEY: str = os.environ.get("ASI_ONE_API_KEY", "").strip()

# ── Stable seeds + ports ───────────────────────────────────────────
LIBRARIAN_SEED = os.environ.get("LIBRARIAN_SEED", "baseline-librarian-seed-v1")
RECOVERY_SEED = os.environ.get("RECOVERY_SEED", "baseline-recovery-seed-v1")
PERFORMANCE_SEED = os.environ.get("PERFORMANCE_SEED", "baseline-performance-seed-v1")
SPONSORSHIP_SEED = os.environ.get("SPONSORSHIP_SEED", "baseline-sponsorship-seed-v1")
ORCHESTRATOR_SEED = os.environ.get("ORCHESTRATOR_SEED", "baseline-orchestrator-seed-v1")

LIBRARIAN_PORT = int(os.environ.get("LIBRARIAN_PORT", "8001"))
RECOVERY_PORT = int(os.environ.get("RECOVERY_PORT", "8002"))
ORCHESTRATOR_PORT = int(os.environ.get("ORCHESTRATOR_PORT", "8003"))
PERFORMANCE_PORT = int(os.environ.get("PERFORMANCE_PORT", "8004"))
SPONSORSHIP_PORT = int(os.environ.get("SPONSORSHIP_PORT", "8005"))


def require_anthropic_key() -> str:
    """Fail fast with a clear message if the Claude key is missing."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy Backend/.env.example to "
            "Backend/.env and fill it in (get a key at console.anthropic.com)."
        )
    return key
