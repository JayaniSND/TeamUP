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
def _env_addr(name: str) -> str:
    """Read an agent address from env, tolerating inline `#` comments and
    whitespace (common in hand-edited .env files). A uAgents address starts
    with 'agent1'; anything else (a stray comment, blank) resolves to ''."""
    val = os.environ.get(name, "").split("#", 1)[0].strip()
    return val if val.startswith("agent1") else ""


LIBRARIAN_ADDRESS: str = _env_addr("LIBRARIAN_ADDRESS")
RECOVERY_ADDRESS: str = _env_addr("RECOVERY_ADDRESS")
PERFORMANCE_ADDRESS: str = _env_addr("PERFORMANCE_ADDRESS")
SPONSORSHIP_ADDRESS: str = _env_addr("SPONSORSHIP_ADDRESS")
LOGISTICS_ADDRESS: str = _env_addr("LOGISTICS_ADDRESS")  # external logistics agent


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
