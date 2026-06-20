"""Shared configuration for the Dev 3 agent layer.

Single source of truth for the section enum, model ids, backend URL, and
agent addresses. Everything reads from the environment (.env), so the
three agents stay in sync without hardcoded values scattered around.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

# Load Backend/.env if present. Looks in CWD and parents, so running an
# agent from either Backend/ or the repo root both work.
load_dotenv()

# The section taxonomy. MUST match Dev 2's `SECTIONS` constant and the
# frontend's copy exactly — it's the contract the Librarian classifies into.
SECTIONS: list[str] = [
    "performance",
    "injury_log",
    "coaching",
    "energy_nutrition",
    "logistics",
    "training",
]

# Sections that trigger downstream specialist agents.
INJURY_SECTIONS = {"injury_log"}
LOGISTICS_SECTIONS = {"logistics"}

# Dev 2's FastAPI. Defaults to the bundled mock backend.
BACKEND_URL: str = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")

# Athlete to attribute entries to when a dump doesn't carry one.
DEFAULT_USER_ID: str = os.environ.get("DEFAULT_USER_ID", "demo-athlete")

# Downstream agent addresses (filled in after first boot — see README).
LIBRARIAN_ADDRESS: str = os.environ.get("LIBRARIAN_ADDRESS", "").strip()
RECOVERY_ADDRESS: str = os.environ.get("RECOVERY_ADDRESS", "").strip()
LOGISTICS_ADDRESS: str = os.environ.get("LOGISTICS_ADDRESS", "").strip()

# Models. Project defaults: cheap/fast classify, stronger synthesis.
CLASSIFY_MODEL: str = os.environ.get("CLASSIFY_MODEL", "claude-haiku-4-5")
SYNTHESIS_MODEL: str = os.environ.get("SYNTHESIS_MODEL", "claude-sonnet-4-6")

# ASI:One bonus router.
ASI_ONE_API_KEY: str = os.environ.get("ASI_ONE_API_KEY", "").strip()

# Fixed seeds keep each agent's address stable across restarts, so the
# addresses you paste into .env don't change every boot.
LIBRARIAN_SEED = os.environ.get("LIBRARIAN_SEED", "baseline-librarian-seed-v1")
RECOVERY_SEED = os.environ.get("RECOVERY_SEED", "baseline-recovery-seed-v1")
ORCHESTRATOR_SEED = os.environ.get("ORCHESTRATOR_SEED", "baseline-orchestrator-seed-v1")

# Ports each agent binds locally.
LIBRARIAN_PORT = int(os.environ.get("LIBRARIAN_PORT", "8001"))
RECOVERY_PORT = int(os.environ.get("RECOVERY_PORT", "8002"))
ORCHESTRATOR_PORT = int(os.environ.get("ORCHESTRATOR_PORT", "8003"))


def require_anthropic_key() -> str:
    """Fail fast with a clear message if the Claude key is missing."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy Backend/.env.example to "
            "Backend/.env and fill it in (get a key at console.anthropic.com)."
        )
    return key
