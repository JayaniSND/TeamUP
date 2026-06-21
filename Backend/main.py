"""Real FastAPI backend — reads/writes Supabase instead of in-memory dicts.

Drop-in replacement for mock_backend.py. Point BACKEND_URL at this service
and the agents + frontend work without any other changes.

Run:
    uvicorn main:app --reload --port 8000     (from Backend/)

Tables must exist in Supabase before running. SQL to create them:

    create table if not exists entries (
      id uuid primary key default gen_random_uuid(),
      user_id text not null,
      raw_input_id text,
      section text not null,
      text text not null,
      metadata jsonb default '{}',
      embedded boolean default false,
      created_at timestamptz default now()
    );
    create table if not exists raw_inputs (
      id uuid primary key default gen_random_uuid(),
      user_id text not null,
      input_type text,
      raw_text text,
      created_at timestamptz default now()
    );
    create table if not exists training_sessions (
      id uuid primary key default gen_random_uuid(),
      user_id text not null,
      date date,
      sport text,
      session_type text,
      duration_minutes int,
      intensity int,
      focus_area text,
      notes text,
      created_at timestamptz default now()
    );
    create table if not exists match_results (
      id uuid primary key default gen_random_uuid(),
      user_id text not null,
      date date,
      opponent text,
      event_name text,
      result text,
      score text,
      key_stats jsonb default '{}',
      notes text,
      created_at timestamptz default now()
    );
    create table if not exists recovery_logs (
      id uuid primary key default gen_random_uuid(),
      user_id text not null,
      date date,
      soreness_level int,
      fatigue_level int,
      sleep_hours float,
      injury_area text,
      pain_level int,
      risk_level text,
      notes text,
      created_at timestamptz default now()
    );
    create table if not exists metrics (
      id uuid primary key default gen_random_uuid(),
      user_id text not null,
      metric_name text,
      metric_value float,
      unit text,
      date date,
      created_at timestamptz default now()
    );
    create table if not exists calendar_events (
      id uuid primary key default gen_random_uuid(),
      user_id text not null,
      title text,
      event_type text,
      start_time timestamptz,
      end_time timestamptz,
      location text,
      source text,
      metadata jsonb default '{}',
      created_at timestamptz default now()
    );
    create table if not exists sponsorship_opportunities (
      id uuid primary key default gen_random_uuid(),
      user_id text not null,
      brand_name text,
      category text,
      contact_email text,
      fit_score float,
      reason text,
      status text default 'suggested',
      draft_email text,
      created_at timestamptz default now()
    );
    create table if not exists agent_outputs (
      id uuid primary key default gen_random_uuid(),
      user_id text not null,
      agent_name text,
      section text,
      summary text,
      severity text default 'info',
      recommended_action text,
      related_entry_ids jsonb default '[]',
      created_at timestamptz default now()
    );
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import anthropic
import sentry_sdk
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

# ── Sentry (optional — only init if DSN is present) ────────────────
_sentry_dsn = os.environ.get("SENTRY_DSN", "").strip()
if _sentry_dsn:
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[FastApiIntegration()],
        traces_sample_rate=1.0,
        environment="hackathon",
        release="baseline@1.0.0",
    )

# ── Supabase client ────────────────────────────────────────────────
from database import supabase  # noqa: E402  (after load_dotenv)

app = FastAPI(title="BASELINE real backend (Supabase)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_SECTIONS = [
    "training", "performance", "match_results", "recovery",
    "coaching", "logistics", "sponsorship", "goals", "media_notes",
]

DEMO_USER_ID = os.environ.get("DEFAULT_USER_ID", "demo-athlete")


# ── Claude helpers (same as mock_backend) ──────────────────────────

def _extract_image_text(image_data: str, media_type: str) -> str:
    resp = anthropic.Anthropic().messages.create(
        model=os.environ.get("SYNTHESIS_MODEL", "claude-sonnet-4-6"),
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_data}},
                {"type": "text", "text": (
                    "Transcribe all handwritten or printed text in this image exactly as written. "
                    "Output only the transcription, no commentary, no markdown formatting."
                )},
            ],
        }],
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def _classify_entries(raw_text: str) -> list[dict]:
    schema = {
        "type": "object",
        "properties": {
            "entries": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "section": {"type": "string", "enum": _SECTIONS},
                        "text": {"type": "string"},
                    },
                    "required": ["section", "text"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["entries"],
        "additionalProperties": False,
    }
    resp = anthropic.Anthropic().messages.create(
        model=os.environ.get("CLASSIFY_MODEL", "claude-haiku-4-5"),
        max_tokens=2048,
        system=(
            "You are the Librarian for an individual athlete's sports analytics dashboard. "
            "Split the athlete's raw input into discrete entries. Each entry is one coherent "
            "thought filed under exactly one section. Preserve meaning; lightly clean filler "
            "words; do not invent content."
        ),
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": raw_text}],
    )
    text_out = next((b.text for b in resp.content if b.type == "text"), "{}")
    return [e for e in json.loads(text_out).get("entries", [])
            if e.get("section") in _SECTIONS and e.get("text")]


# ── Supabase helpers ───────────────────────────────────────────────

def _query(table: str, user_id: str, limit: int, section: str | None = None) -> list[dict]:
    """Fetch rows for a user, newest-first, optional section filter."""
    q = supabase.table(table).select("*").eq("user_id", user_id)
    if section:
        q = q.eq("section", section)
    # prefer created_at; fall back to date for tables that only have a date column
    try:
        result = q.order("created_at", desc=True).limit(limit).execute()
    except Exception:
        result = q.limit(limit).execute()
    if sentry_sdk.is_initialized() and not result.data:
        sentry_sdk.set_context("query", {"table": table, "user_id": user_id})
    return result.data or []


def _norm_entry(row: dict) -> dict:
    """Normalize a Supabase entries row to the agent-facing shape."""
    return {
        "entry_id": row.get("id") or row.get("entry_id"),
        "user_id": row.get("user_id"),
        "section": row.get("section"),
        "text": row.get("text"),
        "raw_input_id": row.get("raw_input_id"),
        "ts": row.get("created_at") or row.get("ts"),
        "meta": row.get("metadata") or row.get("meta") or {},
    }


def _norm_output(row: dict) -> dict:
    return {
        "output_id": row.get("id") or row.get("output_id"),
        "user_id": row.get("user_id"),
        "agent_name": row.get("agent_name"),
        "section": row.get("section"),
        "summary": row.get("summary"),
        "severity": row.get("severity", "info"),
        "recommended_action": row.get("recommended_action", ""),
        "related_entry_ids": row.get("related_entry_ids") or [],
        "ts": row.get("created_at") or row.get("ts"),
    }


# ── Pydantic models ────────────────────────────────────────────────

class EntryIn(BaseModel):
    user_id: str
    section: str
    text: str
    meta: dict = {}


class AgentOutputIn(BaseModel):
    user_id: str
    agent_name: str
    section: str
    summary: str
    severity: str = "info"
    recommended_action: str = ""
    related_entry_ids: list = []


class SponsorshipIn(BaseModel):
    user_id: str
    brand_name: str = ""
    category: str = ""
    contact_email: str = ""
    fit_score: float = 0.0
    reason: str = ""
    status: str = "suggested"
    draft_email: str = ""


class IngestIn(BaseModel):
    user_id: str = "demo-athlete"
    input_type: str
    text: str | None = None
    image_data: str | None = None
    image_media_type: str = "image/jpeg"


class ChatIn(BaseModel):
    user_id: str
    question: str


# ── Core endpoints ─────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest")
def ingest(body: IngestIn):
    if body.input_type not in ("text", "image", "voice"):
        return {"error": "input_type must be 'text', 'image', or 'voice'"}

    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if body.input_type == "image":
        if not body.image_data:
            return {"error": "image_data (base64) required for input_type='image'"}
        if not api_key:
            return {"error": "ANTHROPIC_API_KEY required for image ingestion"}
        raw_text = _extract_image_text(body.image_data, body.image_media_type)
    else:
        if not body.text or not body.text.strip():
            return {"error": "text required for input_type='text' or 'voice'"}
        raw_text = body.text.strip()

    if not raw_text:
        return {"error": "No text extracted or provided"}

    entries_data = _classify_entries(raw_text) if api_key else [{"section": "training", "text": raw_text}]

    ts = datetime.now(timezone.utc).isoformat()

    raw_result = supabase.table("raw_inputs").insert({
        "user_id": body.user_id,
        "input_type": body.input_type,
        "raw_text": raw_text,
        "created_at": ts,
    }).execute()
    raw_input_id = (raw_result.data or [{}])[0].get("id")

    written = []
    for e in entries_data:
        res = supabase.table("entries").insert({
            "user_id": body.user_id,
            "section": e["section"],
            "text": e["text"],
            "raw_input_id": str(raw_input_id) if raw_input_id else None,
            "metadata": {},
            "embedded": False,
            "created_at": ts,
        }).execute()
        row = (res.data or [{}])[0]
        written.append({"entry_id": row.get("id"), "section": e["section"], "text": e["text"]})

    return {
        "raw_input_id": raw_input_id,
        "input_type": body.input_type,
        "entries_count": len(written),
        "sections": sorted({e["section"] for e in written}),
        "entries": written,
    }


@app.post("/entries")
def create_entry(e: EntryIn):
    res = supabase.table("entries").insert({
        "user_id": e.user_id,
        "section": e.section,
        "text": e.text,
        "metadata": e.meta,
        "embedded": False,
    }).execute()
    row = (res.data or [{}])[0]
    return {"entry_id": row.get("id")}


@app.get("/entries")
def list_entries(user_id: str, section: str | None = None, limit: int = 20):
    rows = _query("entries", user_id, limit, section)
    return [_norm_entry(r) for r in rows]


@app.get("/metrics")
def list_metrics(user_id: str, limit: int = 20):
    return _query("metrics", user_id, limit)


@app.get("/match_results")
def list_matches(user_id: str, limit: int = 20):
    return _query("match_results", user_id, limit)


@app.get("/training_sessions")
def list_training(user_id: str, limit: int = 20):
    return _query("training_sessions", user_id, limit)


@app.get("/recovery_logs")
def list_recovery(user_id: str, limit: int = 20):
    return _query("recovery_logs", user_id, limit)


@app.get("/athlete_profile")
def get_profile(user_id: str):
    return {
        "user_id": user_id,
        "name": "Demo Athlete",
        "sport": "Tennis",
        "level": "College",
        "location": "San Jose, CA",
        "dominant_side": "right",
        "goals": ["Win a regional open", "Improve serve consistency"],
        "strengths": ["Forehand", "Court coverage"],
        "weaknesses": ["Second serve", "Net play"],
        "injury_history": ["Right knee tendinitis (2025)"],
    }


@app.post("/agent_outputs")
def create_agent_output(o: AgentOutputIn):
    res = supabase.table("agent_outputs").insert({
        "user_id": o.user_id,
        "agent_name": o.agent_name,
        "section": o.section,
        "summary": o.summary,
        "severity": o.severity,
        "recommended_action": o.recommended_action,
        "related_entry_ids": o.related_entry_ids,
    }).execute()
    row = (res.data or [{}])[0]
    return {"output_id": row.get("id")}


@app.get("/agent_outputs")
def list_agent_outputs(user_id: str, limit: int = 20):
    rows = _query("agent_outputs", user_id, limit)
    return [_norm_output(r) for r in rows]


@app.post("/sponsorship_opportunities")
def create_sponsorship(s: SponsorshipIn):
    res = supabase.table("sponsorship_opportunities").insert(s.model_dump()).execute()
    row = (res.data or [{}])[0]
    return {"opportunity_id": row.get("id")}


# ── Dashboard endpoints ────────────────────────────────────────────

@app.get("/dashboard/overview")
def dashboard_overview(user_id: str):
    matches = _query("match_results", user_id, 20)
    wins = sum(1 for m in matches if m.get("result") == "win")
    losses = sum(1 for m in matches if m.get("result") == "loss")
    agent_outputs = _query("agent_outputs", user_id, 5)
    return {
        "athlete": {"name": "Demo Athlete", "sport": "Tennis", "level": "College"},
        "summary_cards": {
            "weekly_load": "High",
            "recovery_risk": "Medium",
            "next_event": "San Jose Open - Saturday",
            "recent_results": f"{wins} Wins / {losses} Losses",
            "ai_focus": "Serve consistency + knee recovery",
        },
        "latest_agent_outputs": [_norm_output(r) for r in agent_outputs],
    }


@app.get("/dashboard/performance")
def dashboard_performance(user_id: str):
    matches = _query("match_results", user_id, 20)
    metric_rows = _query("metrics", user_id, 50)
    by_name: dict[str, list] = {}
    for m in metric_rows:
        by_name.setdefault(m["metric_name"], []).append(
            {"date": m.get("date"), "value": m.get("metric_value")}
        )
    agent_outputs = _query("agent_outputs", user_id, 10)
    return {
        "win_loss": [{"date": m.get("date"), "result": m.get("result")} for m in matches],
        "metrics": [{"metric_name": n, "data": d} for n, d in by_name.items()],
        "insights": [_norm_output(o) for o in agent_outputs if o.get("section") == "performance"],
    }


@app.get("/dashboard/recovery")
def dashboard_recovery(user_id: str):
    agent_outputs = _query("agent_outputs", user_id, 10)
    return {
        "recovery_logs": _query("recovery_logs", user_id, 20),
        "insights": [_norm_output(o) for o in agent_outputs if o.get("section") == "recovery"],
    }


@app.get("/dashboard/matches")
def dashboard_matches(user_id: str):
    return {"matches": _query("match_results", user_id, 20)}


@app.get("/dashboard/training")
def dashboard_training(user_id: str):
    return {"sessions": _query("training_sessions", user_id, 20)}


@app.get("/dashboard/logistics")
def dashboard_logistics(user_id: str):
    return {"events": _query("calendar_events", user_id, 20)}


@app.get("/dashboard/sponsorship")
def dashboard_sponsorship(user_id: str):
    return {"opportunities": _query("sponsorship_opportunities", user_id, 20)}


# ── /chat : recency-based RAG (no Redis required) ──────────────────
# Pulls the 15 most recent entries and sends them to Claude with the
# question. Good enough for demo; swap retrieve() for RedisVL KNN
# when the embed pipeline is ready.

@app.post("/chat")
def chat(body: ChatIn):
    rows = _query("entries", body.user_id, 15)
    entries = [_norm_entry(r) for r in rows]
    if not entries:
        return {"answer": "I don't have any journal entries for you yet.", "sources": []}

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        joined = "; ".join(e["text"] for e in entries[:5])
        return {"answer": f"(no ANTHROPIC_API_KEY set) Recent entries: {joined}",
                "sources": [e["entry_id"] for e in entries[:5]]}

    context = "\n\n".join(f"[{e['section'].upper()}] {e['text']}" for e in entries)
    prompt = (
        "You are a sports performance analyst reviewing an athlete's journal. "
        "Answer using ONLY the entries below. Be specific — quote what they wrote. "
        "If the entries lack enough information, say so.\n\n"
        f"JOURNAL ENTRIES:\n{context}\n\nQUESTION: {body.question}"
    )
    with sentry_sdk.start_span(op="ai.inference", description="Claude chat generation") if sentry_sdk.is_initialized() else _noop():
        resp = anthropic.Anthropic().messages.create(
            model=os.environ.get("SYNTHESIS_MODEL", "claude-sonnet-4-6"),
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
    answer = next((b.text for b in resp.content if b.type == "text"), "")
    return {"answer": answer, "sources": [e["entry_id"] for e in entries]}


# ── Demo seed endpoint ─────────────────────────────────────────────
# POST /admin/seed   → inserts the same demo data as mock_backend._seed()
# POST /admin/clear  → deletes all rows for the demo user

@app.post("/admin/seed")
def admin_seed(user_id: str = DEMO_USER_ID):
    """Insert linguistic-drift trail, burnout arc, matches, training, recovery, metrics, calendar."""
    def _ts(days_ago: int) -> str:
        return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()

    def _date(days_ago: int) -> str:
        return (datetime.now(timezone.utc) - timedelta(days=days_ago)).date().isoformat()

    inserted: dict[str, int] = {}

    # Serve linguistic-drift (physical fatigue — no explicit pain words)
    serve_entries = [
        ("training", "Serve felt explosive today, easy power, snapping through the ball.", 14),
        ("performance", "First serves were popping — free points all session.", 13),
        ("training", "Good serve rhythm, felt effortless and loose.", 11),
        ("training", "Serve was okay, had to work a bit harder for pace.", 9),
        ("performance", "Serve felt heavy, kind of grinding through it today.", 7),
        ("training", "Really muscling the serve now, shoulder feels tight afterward.", 4),
        ("training", "Pushed through another long serving block, no rest day this week.", 2),
        ("performance", "Serve speed up on paper but it's costing me — arm feels dead.", 1),
    ]
    knee_entries = [
        ("recovery", "Right knee a bit sore after hill repeats.", 6),
        ("training", "60 min on court, lots of footwork drills.", 6),
        ("recovery", "Knee still tender during warmup, pushed through.", 4),
        ("recovery", "Right knee sore again after the long session.", 2),
        ("performance", "Serve felt sharp in practice.", 2),
    ]
    # Emotional arc (burnout → recovery → readiness)
    arc_entries = [
        ("goals", "Honestly thinking about quitting. Losing so much, I don't know why I'm even playing.", 45),
        ("coaching", "Dragged myself to practice, heart's just not in it right now.", 38),
        ("coaching", "Coach said simplify and have fun. Tried to just enjoy hitting today.", 30),
        ("performance", "Starting to feel a bit more like myself on court.", 20),
        ("performance", "Best session in weeks — movement felt sharp and free.", 12),
        ("media_notes", "Confidence is back, serves were snapping, won a practice set easily.", 6),
        ("goals", "Feeling really good and motivated — I want to compete again.", 3),
    ]

    entry_rows = [
        {"user_id": user_id, "section": s, "text": t, "metadata": {}, "embedded": False, "created_at": _ts(d)}
        for s, t, d in [*serve_entries, *knee_entries, *arc_entries]
    ]
    r = supabase.table("entries").insert(entry_rows).execute()
    inserted["entries"] = len(r.data or [])

    matches = [
        {"user_id": user_id, "date": _date(12), "opponent": "A. Rivera", "event_name": "Local Ladder", "result": "win", "score": "6-3, 6-4", "key_stats": {}, "notes": ""},
        {"user_id": user_id, "date": _date(8),  "opponent": "K. Tanaka", "event_name": "Local Ladder", "result": "loss", "score": "4-6, 3-6", "key_stats": {}, "notes": ""},
        {"user_id": user_id, "date": _date(5),  "opponent": "M. Lopez",  "event_name": "Local Ladder", "result": "win",  "score": "7-5, 6-2", "key_stats": {}, "notes": ""},
    ]
    r = supabase.table("match_results").insert(matches).execute()
    inserted["match_results"] = len(r.data or [])

    sessions = [
        {"user_id": user_id, "date": _date(6), "sport": "Tennis", "session_type": "drills",      "duration_minutes": 60, "intensity": 6, "focus_area": "serve", "notes": ""},
        {"user_id": user_id, "date": _date(4), "sport": "Tennis", "session_type": "match play",  "duration_minutes": 90, "intensity": 8, "focus_area": "serve", "notes": ""},
        {"user_id": user_id, "date": _date(2), "sport": "Tennis", "session_type": "intervals",   "duration_minutes": 75, "intensity": 9, "focus_area": "serve", "notes": ""},
    ]
    r = supabase.table("training_sessions").insert(sessions).execute()
    inserted["training_sessions"] = len(r.data or [])

    rec_logs = [
        {"user_id": user_id, "date": _date(6), "soreness_level": 3, "fatigue_level": 3, "sleep_hours": 7.5, "injury_area": "right knee", "pain_level": 2, "risk_level": "low",    "notes": ""},
        {"user_id": user_id, "date": _date(4), "soreness_level": 5, "fatigue_level": 5, "sleep_hours": 6.0, "injury_area": "right knee", "pain_level": 4, "risk_level": "medium", "notes": ""},
        {"user_id": user_id, "date": _date(2), "soreness_level": 7, "fatigue_level": 6, "sleep_hours": 5.5, "injury_area": "right knee", "pain_level": 5, "risk_level": "high",   "notes": ""},
    ]
    r = supabase.table("recovery_logs").insert(rec_logs).execute()
    inserted["recovery_logs"] = len(r.data or [])

    metric_rows = [
        {"user_id": user_id, "metric_name": "serve_speed",     "metric_value": 82, "unit": "mph", "date": _date(6)},
        {"user_id": user_id, "metric_name": "serve_speed",     "metric_value": 85, "unit": "mph", "date": _date(2)},
        {"user_id": user_id, "metric_name": "training_load",   "metric_value": 4,  "unit": "au",  "date": _date(6)},
        {"user_id": user_id, "metric_name": "training_load",   "metric_value": 9,  "unit": "au",  "date": _date(2)},
        {"user_id": user_id, "metric_name": "recovery_score",  "metric_value": 78, "unit": "pct", "date": _date(6)},
        {"user_id": user_id, "metric_name": "recovery_score",  "metric_value": 55, "unit": "pct", "date": _date(2)},
    ]
    r = supabase.table("metrics").insert(metric_rows).execute()
    inserted["metrics"] = len(r.data or [])

    cal = [{
        "user_id": user_id,
        "title": "San Jose Open",
        "event_type": "tournament",
        "start_time": _ts(-7),
        "end_time": _ts(-6),
        "location": "San Jose, CA",
        "source": "seed",
        "metadata": {},
    }]
    r = supabase.table("calendar_events").insert(cal).execute()
    inserted["calendar_events"] = len(r.data or [])

    return {"seeded": inserted, "user_id": user_id}


@app.post("/admin/clear")
def admin_clear(user_id: str = DEMO_USER_ID):
    """Delete all rows for a user — use before re-seeding."""
    tables = [
        "entries", "raw_inputs", "training_sessions", "match_results",
        "recovery_logs", "metrics", "calendar_events",
        "sponsorship_opportunities", "agent_outputs",
    ]
    deleted: dict[str, int] = {}
    for table in tables:
        r = supabase.table(table).delete().eq("user_id", user_id).execute()
        deleted[table] = len(r.data or [])
    return {"cleared": deleted, "user_id": user_id}


# ── Sentry span context manager shim ──────────────────────────────

class _noop:
    def __enter__(self): return self
    def __exit__(self, *_): pass
