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
import logging
import mimetypes
import os
from datetime import datetime, timedelta, timezone

import anthropic
import sentry_sdk
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

import rag  # noqa: E402 — after load_dotenv so REDIS_URL is available

log = logging.getLogger("main")

# ── Sentry (optional — only init if DSN is present) ────────────────
# Integrations are best-effort: a missing optional dep (e.g. SQLAlchemy, which
# this project doesn't use — it talks to Supabase over REST) must NOT crash the
# whole API on import. Each integration is loaded defensively and skipped if its
# backing package isn't installed.
_sentry_dsn = os.environ.get("SENTRY_DSN", "").strip()
if _sentry_dsn:
    _sentry_integrations = []
    for _import_integration in (
        lambda: __import__("sentry_sdk.integrations.fastapi", fromlist=["FastApiIntegration"]).FastApiIntegration(),
        lambda: __import__("sentry_sdk.integrations.sqlalchemy", fromlist=["SqlalchemyIntegration"]).SqlalchemyIntegration(),
    ):
        try:
            _sentry_integrations.append(_import_integration())
        except Exception as _e:  # noqa: BLE001 — optional integration, skip if unavailable
            log.warning("sentry integration skipped: %s", _e)
    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=_sentry_integrations,
        traces_sample_rate=1.0,
        environment="hackathon",
        release="baseline@1.0.0",
    )

# ── Supabase client ────────────────────────────────────────────────
from database import supabase  # noqa: E402  (after load_dotenv)

# ── Service layer (Supabase data access + HTTP Orchestrator brain) ──
from services import athlete_context, booking_service, orchestrator_service  # noqa: E402

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


class OrchestratorChatIn(BaseModel):
    """Single chat request from the frontend. The frontend sends only the raw
    message + identity/context — it never selects an agent."""
    user_id: str = DEMO_USER_ID
    message: str
    session_id: str | None = None
    context: dict = {}  # optional frontend hints (e.g. {"page": "/dashboard"})


class BookingOptionIn(BaseModel):
    kind: str                      # 'flight' | 'hotel' | 'tournament_entry'
    title: str
    location: str | None = None
    amount_cents: int
    currency: str = "usd"
    description: str | None = None
    start_date: str | None = None
    start_time: str | None = None
    end_date: str | None = None
    end_time: str | None = None
    provider: str | None = None


class CheckoutIn(BaseModel):
    user_id: str = DEMO_USER_ID
    option: BookingOptionIn


class ConfirmBookingIn(BaseModel):
    session_id: str


class CalendarIn(BaseModel):
    user_id: str
    title: str
    event_type: str = "tournament"
    start_time: str = ""
    end_time: str = ""
    location: str = ""
    source: str = "agent"
    metadata: dict = {}


# ── Core endpoints ─────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


# ── Photo / voice → text (frontend Upload page) ────────────────────
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".heic", ".heif", ".tif", ".tiff"}
TEXT_NOTE_EXTS = {".txt", ".md", ".markdown", ".text"}
AUDIO_EXTS = {".webm", ".wav", ".mp3", ".m4a", ".mp4", ".ogg", ".oga", ".opus", ".flac", ".aac", ".aiff", ".aif"}


@app.post("/convert/photo")
async def convert_photo(file: UploadFile = File(...)):
    """Image/note file → extracted text (Claude vision OCR). Returns {"text": ...}."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="No file uploaded, or the file is empty.")

    name = (file.filename or "").lower()
    ext = os.path.splitext(name)[1]
    ctype = (file.content_type or "").lower()

    if ctype.startswith("text/") or ext in TEXT_NOTE_EXTS:
        return {"text": data.decode("utf-8", errors="replace").strip()}

    if not (ctype.startswith("image/") or ext in IMAGE_EXTS):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type for photo/note upload: "
                f"{file.content_type or ext or 'unknown'}. Upload an image or a .txt/.md note."
            ),
        )

    media_type = ctype if ctype.startswith("image/") else (mimetypes.guess_type(name)[0] or "image/jpeg")
    from agents.processing.phototext import extract_text_from_image_bytes

    try:
        text = extract_text_from_image_bytes(data, media_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Image conversion failed: {e}")

    return {"text": text}


@app.post("/convert/voice")
async def convert_voice(file: UploadFile = File(...)):
    """Audio file/recording → transcript (Deepgram). Returns {"text": ...}."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="No audio uploaded, or the file is empty.")

    name = (file.filename or "").lower()
    ext = os.path.splitext(name)[1]
    ctype = (file.content_type or "").lower()

    if not (ctype.startswith("audio/") or ctype.startswith("video/") or ext in AUDIO_EXTS):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported audio type: {file.content_type or ext or 'unknown'}. "
                "Record audio or upload webm / wav / mp3 / m4a / ogg / flac."
            ),
        )

    from agents.processing.voicetotext import transcribe_audio_bytes

    try:
        text = transcribe_audio_bytes(data, ctype or None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Voice conversion failed: {e}")

    return {"text": text}


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
        entry_id = row.get("id")
        stored = rag.store_entry(entry_id, body.user_id, e["section"], e["text"])
        if stored and entry_id:
            supabase.table("entries").update({"embedded": True}).eq("id", entry_id).execute()
        written.append({"entry_id": entry_id, "section": e["section"], "text": e["text"]})

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
    entry_id = row.get("id")

    stored = rag.store_entry(entry_id, e.user_id, e.section, e.text)
    if stored and entry_id:
        supabase.table("entries").update({"embedded": True}).eq("id", entry_id).execute()

    return {"entry_id": entry_id}


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
    """Real profile from Supabase if an `athlete_profiles` table exists, else an
    honest placeholder (no fabricated identity). See athlete_context.get_athlete_profile."""
    return athlete_context.get_athlete_profile(user_id)


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


@app.post("/calendar/add")
def add_calendar_event(c: CalendarIn):
    res = supabase.table("calendar_events").insert(c.model_dump()).execute()
    row = (res.data or [{}])[0]
    return {"event_id": row.get("id")}


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


# ── /chat : RAG + LangCache ────────────────────────────────────────
# 1. Check LangCache — if a semantically similar question was answered
#    recently, return it immediately (no embed, no KNN, no Claude call).
# 2. Retrieve — KNN search over RedisVL for the athlete's entries most
#    semantically similar to the question. Falls back to recency query
#    if Redis is not connected.
# 3. Generate — Claude reads the retrieved entries and answers. Answer
#    is grounded in actual journal text, not generic sports knowledge.
# 4. Cache — store (question, answer) in LangCache for future hits.

@app.post("/chat")
def chat(body: ChatIn):
    """Standalone RAG Q&A (the orchestrator's 'ask' path). Shares one
    implementation with the orchestrator so both stay in sync."""
    with sentry_sdk.start_span(op="ai.inference", description="Claude chat") if sentry_sdk.is_initialized() else _noop():
        return orchestrator_service.answer_question(body.user_id, body.question)


# ── /orchestrator/chat : the frontend's single AI entry point ──────
# The frontend sends EVERY chat message here with only { user_id, message,
# session_id?, context? }. The orchestrator loads the athlete's real Supabase
# context, classifies intent, and routes to the right specialist analysis
# function — the frontend never chooses an agent. Returns a structured reply:
#   { message, intent, agents_used, athlete_context_summary, warnings,
#     suggested_actions, sources }

@app.post("/orchestrator/chat")
async def orchestrator_chat(body: OrchestratorChatIn):
    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="`message` is required.")
    return await orchestrator_service.run_orchestrator(
        user_id=body.user_id,
        message=body.message,
        session_id=body.session_id,
        context=body.context,
    )


# ── Travel booking → Stripe Checkout (test mode) ───────────────────
# The chat surfaces representative options; the athlete clicks Book & Pay, pays
# on Stripe's hosted test page (no real charge), and returns to confirm.

@app.post("/bookings/checkout")
def bookings_checkout(body: CheckoutIn):
    """Record a pending booking and open a Stripe test Checkout Session."""
    return booking_service.create_checkout_session(body.user_id, body.option.model_dump())


@app.post("/bookings/confirm")
def bookings_confirm(body: ConfirmBookingIn):
    """Verify a returned Checkout Session and mark the booking paid."""
    return booking_service.confirm_checkout(body.session_id)


@app.get("/bookings")
def list_bookings(user_id: str = DEMO_USER_ID):
    return {"bookings": booking_service.list_bookings(user_id)}


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


@app.post("/admin/backfill")
def admin_backfill(user_id: str = DEMO_USER_ID):
    """Embed and store in RedisVL all entries that haven't been vectorised yet.

    Run this once after /admin/seed if Redis wasn't connected during seeding,
    or whenever entries land in Supabase outside the normal POST /entries flow.
    """
    if not rag.REDIS_URL:
        return {"error": "REDIS_URL not set — RedisVL unavailable"}

    rows = supabase.table("entries").select("*").eq("user_id", user_id).eq("embedded", False).execute()
    entries = [_norm_entry(r) for r in (rows.data or [])]
    stored = rag.backfill_entries(entries)

    if stored:
        ids = [e["entry_id"] for e in entries[:stored]]
        supabase.table("entries").update({"embedded": True}).in_("id", ids).execute()

    return {"backfilled": stored, "total_unembedded": len(entries), "user_id": user_id}


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
