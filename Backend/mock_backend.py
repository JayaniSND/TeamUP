"""Local stand-in for Dev 2's FastAPI, so the agent chain is runnable solo.

Implements just the endpoints the Dev 3 agents call, with an in-memory store
seeded with a believable injury history (knee sore across several sessions)
so the Recovery agent has a real pattern to detect in a demo.

This is a developer convenience, NOT the real backend — when Dev 2's service
is up, point BACKEND_URL at it and delete nothing here.

Run:  uvicorn mock_backend:app --reload   (from the Backend/ directory)
"""

from __future__ import annotations

import itertools
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="BASELINE mock backend (Dev 2 stand-in)")

_ids = itertools.count(1)
_entries: list[dict] = []
_metrics: list[dict] = []
_flags: list[dict] = []


def _seed():
    """A week of history so Recovery can detect a real overtraining pattern."""
    now = datetime.now(timezone.utc)
    seed_notes = [
        ("injury_log", "Right knee a bit sore after hill repeats.", 6),
        ("training", "60 min on court, lots of footwork drills.", 6),
        ("injury_log", "Knee still tender during warmup, pushed through.", 4),
        ("injury_log", "Right knee sore again after the long session.", 2),
    ]
    for section, text, days_ago in seed_notes:
        _entries.append(
            {
                "entry_id": next(_ids),
                "user_id": "demo-athlete",
                "section": section,
                "text": text,
                "ts": (now - timedelta(days=days_ago)).isoformat(),
                "meta": {},
            }
        )
    for days_ago, miles, recovery in [(6, 4, 78), (4, 7, 64), (2, 9, 55)]:
        _metrics.append(
            {
                "metric_id": next(_ids),
                "user_id": "demo-athlete",
                "name": "training_volume_mi",
                "value": miles,
                "ts": (now - timedelta(days=days_ago)).isoformat(),
            }
        )
        _metrics.append(
            {
                "metric_id": next(_ids),
                "user_id": "demo-athlete",
                "name": "recovery_score",
                "value": recovery,
                "ts": (now - timedelta(days=days_ago)).isoformat(),
            }
        )


_seed()


class EntryIn(BaseModel):
    user_id: str
    section: str
    text: str
    meta: dict = {}


class FlagIn(BaseModel):
    user_id: str
    overtraining_risk: bool = False
    severity: str = "none"
    body_parts: list[str] = []
    rationale: str = ""
    recommendation: str = ""


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/entries")
def create_entry(entry: EntryIn):
    row = {
        "entry_id": next(_ids),
        "ts": datetime.now(timezone.utc).isoformat(),
        **entry.model_dump(),
    }
    _entries.append(row)
    return {"entry_id": row["entry_id"]}


@app.get("/entries")
def list_entries(user_id: str, section: str | None = None, limit: int = 20):
    rows = [e for e in _entries if e["user_id"] == user_id]
    if section:
        rows = [e for e in rows if e["section"] == section]
    rows.sort(key=lambda e: e["ts"], reverse=True)
    return rows[:limit]


@app.get("/metrics")
def list_metrics(user_id: str, limit: int = 20):
    rows = [m for m in _metrics if m["user_id"] == user_id]
    rows.sort(key=lambda m: m["ts"], reverse=True)
    return rows[:limit]


@app.post("/recovery_flags")
def create_flag(flag: FlagIn):
    row = {
        "flag_id": next(_ids),
        "ts": datetime.now(timezone.utc).isoformat(),
        **flag.model_dump(),
    }
    _flags.append(row)
    return {"flag_id": row["flag_id"]}


@app.get("/recovery_flags")
def list_flags(user_id: str):
    return [f for f in _flags if f["user_id"] == user_id]
