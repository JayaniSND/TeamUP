"""Local stand-in for the data backend's FastAPI, so the agent chain runs solo.

Implements the endpoints the agents call plus a few dashboard routes, with an
in-memory store seeded with believable athlete history (a knee-soreness pattern
Recovery can detect, a win/loss record Performance can read, a profile for
Sponsorship). This is a developer convenience — point BACKEND_URL at the
real data backend when it's up.

Run:  uvicorn mock_backend:app --reload   (from Backend/)
"""

from __future__ import annotations

import itertools
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

load_dotenv()  # so the /chat RAG stub can read ANTHROPIC_API_KEY

app = FastAPI(title="BASELINE mock backend (data backend stand-in)")

_ids = itertools.count(1)
DB: dict[str, list[dict]] = {
    "entries": [],
    "training_sessions": [],
    "match_results": [],
    "recovery_logs": [],
    "metrics": [],
    "calendar_events": [],
    "sponsorship_opportunities": [],
    "agent_outputs": [],
}
PROFILE = {
    "user_id": "demo-athlete",
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


def _ts(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _seed():
    # Linguistic-drift trail: serve language quietly degrades over 2 weeks with
    # no explicit "pain" word — what the passive Recovery sweep should catch.
    for section, text, days in [
        ("training", "Serve felt explosive today, easy power, snapping through the ball.", 14),
        ("performance", "First serves were popping — free points all session.", 13),
        ("training", "Good serve rhythm, felt effortless and loose.", 11),
        ("training", "Serve was okay, had to work a bit harder for pace.", 9),
        ("performance", "Serve felt heavy, kind of grinding through it today.", 7),
        ("training", "Really muscling the serve now, shoulder feels tight afterward.", 4),
        ("training", "Pushed through another long serving block, no rest day this week.", 2),
        ("performance", "Serve speed up on paper but it's costing me — arm feels dead.", 1),
    ]:
        DB["entries"].append({
            "entry_id": next(_ids), "user_id": "demo-athlete",
            "section": section, "text": text, "ts": _ts(days), "meta": {},
        })
    for section, text, days in [
        ("recovery", "Right knee a bit sore after hill repeats.", 6),
        ("training", "60 min on court, lots of footwork drills.", 6),
        ("recovery", "Knee still tender during warmup, pushed through.", 4),
        ("recovery", "Right knee sore again after the long session.", 2),
        ("performance", "Serve felt sharp in practice.", 2),
    ]:
        DB["entries"].append({
            "entry_id": next(_ids), "user_id": "demo-athlete",
            "section": section, "text": text, "ts": _ts(days), "meta": {},
        })
    for days, opp, result, score in [
        (12, "A. Rivera", "win", "6-3, 6-4"),
        (8, "K. Tanaka", "loss", "4-6, 3-6"),
        (5, "M. Lopez", "win", "7-5, 6-2"),
    ]:
        DB["match_results"].append({
            "match_id": next(_ids), "user_id": "demo-athlete", "date": _ts(days)[:10],
            "opponent": opp, "event_name": "Local Ladder", "result": result,
            "score": score, "key_stats": {}, "notes": "",
        })
    for days, sess, mins, intensity in [(6, "drills", 60, 6), (4, "match play", 90, 8), (2, "intervals", 75, 9)]:
        DB["training_sessions"].append({
            "session_id": next(_ids), "user_id": "demo-athlete", "date": _ts(days)[:10],
            "sport": "Tennis", "session_type": sess, "duration_minutes": mins,
            "intensity": intensity, "focus_area": "serve", "notes": "",
        })
    for days, sore, fatigue, sleep, pain in [(6, 3, 3, 7.5, 2), (4, 5, 5, 6.0, 4), (2, 7, 6, 5.5, 5)]:
        DB["recovery_logs"].append({
            "log_id": next(_ids), "user_id": "demo-athlete", "date": _ts(days)[:10],
            "soreness_level": sore, "fatigue_level": fatigue, "sleep_hours": sleep,
            "injury_area": "right knee", "pain_level": pain, "risk_level": "", "notes": "",
        })
    for days, name, value, unit in [
        (6, "serve_speed", 82, "mph"), (2, "serve_speed", 85, "mph"),
        (6, "training_load", 4, "au"), (2, "training_load", 9, "au"),
        (6, "recovery_score", 78, "pct"), (2, "recovery_score", 55, "pct"),
    ]:
        DB["metrics"].append({
            "metric_id": next(_ids), "user_id": "demo-athlete", "metric_name": name,
            "metric_value": value, "unit": unit, "date": _ts(days)[:10],
        })
    DB["calendar_events"].append({
        "event_id": next(_ids), "user_id": "demo-athlete", "title": "San Jose Open",
        "event_type": "tournament", "start_time": _ts(-7), "end_time": _ts(-6),
        "location": "San Jose, CA", "source": "seed", "metadata": {},
    })


_seed()


# ── models ─────────────────────────────────────────────────────────
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


def _by_user(table: str, user_id: str, limit: int, section: str | None = None):
    rows = [r for r in DB[table] if r.get("user_id") == user_id]
    if section:
        rows = [r for r in rows if r.get("section") == section]
    rows = sorted(rows, key=lambda r: r.get("ts") or r.get("date") or "", reverse=True)
    return rows[:limit]


# ── core endpoints ─────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/entries")
def create_entry(e: EntryIn):
    row = {"entry_id": next(_ids), "ts": datetime.now(timezone.utc).isoformat(), **e.model_dump()}
    DB["entries"].append(row)
    return {"entry_id": row["entry_id"]}


@app.get("/entries")
def list_entries(user_id: str, section: str | None = None, limit: int = 20):
    return _by_user("entries", user_id, limit, section)


@app.get("/metrics")
def list_metrics(user_id: str, limit: int = 20):
    return _by_user("metrics", user_id, limit)


@app.get("/match_results")
def list_matches(user_id: str, limit: int = 20):
    return _by_user("match_results", user_id, limit)


@app.get("/training_sessions")
def list_training(user_id: str, limit: int = 20):
    return _by_user("training_sessions", user_id, limit)


@app.get("/recovery_logs")
def list_recovery(user_id: str, limit: int = 20):
    return _by_user("recovery_logs", user_id, limit)


@app.get("/athlete_profile")
def get_profile(user_id: str):
    return PROFILE if user_id == PROFILE["user_id"] else {"user_id": user_id}


@app.post("/agent_outputs")
def create_agent_output(o: AgentOutputIn):
    row = {"output_id": next(_ids), "ts": datetime.now(timezone.utc).isoformat(), **o.model_dump()}
    DB["agent_outputs"].append(row)
    return {"output_id": row["output_id"]}


@app.get("/agent_outputs")
def list_agent_outputs(user_id: str, limit: int = 20):
    return _by_user("agent_outputs", user_id, limit)


@app.post("/sponsorship_opportunities")
def create_sponsorship(s: SponsorshipIn):
    row = {"opportunity_id": next(_ids), "ts": datetime.now(timezone.utc).isoformat(), **s.model_dump()}
    DB["sponsorship_opportunities"].append(row)
    return {"opportunity_id": row["opportunity_id"]}


# ── dashboard endpoints ────────────────────────────────────────────
@app.get("/dashboard/overview")
def dashboard_overview(user_id: str):
    matches = _by_user("match_results", user_id, 20)
    wins = sum(1 for m in matches if m.get("result") == "win")
    losses = sum(1 for m in matches if m.get("result") == "loss")
    return {
        "athlete": {k: PROFILE.get(k) for k in ("name", "sport", "level")},
        "summary_cards": {
            "weekly_load": "High",
            "recovery_risk": "Medium",
            "next_event": "San Jose Open - Saturday",
            "recent_results": f"{wins} Wins / {losses} Losses",
            "ai_focus": "Serve consistency + knee recovery",
        },
        "latest_agent_outputs": _by_user("agent_outputs", user_id, 5),
    }


@app.get("/dashboard/performance")
def dashboard_performance(user_id: str):
    matches = _by_user("match_results", user_id, 20)
    metric_rows = _by_user("metrics", user_id, 50)
    by_name: dict[str, list] = {}
    for m in metric_rows:
        by_name.setdefault(m["metric_name"], []).append(
            {"date": m["date"], "value": m["metric_value"]}
        )
    return {
        "win_loss": [{"date": m["date"], "result": m["result"]} for m in matches],
        "metrics": [{"metric_name": n, "data": d} for n, d in by_name.items()],
        "insights": [o for o in _by_user("agent_outputs", user_id, 10)
                     if o.get("section") == "performance"],
    }


@app.get("/dashboard/recovery")
def dashboard_recovery(user_id: str):
    return {
        "recovery_logs": _by_user("recovery_logs", user_id, 20),
        "insights": [o for o in _by_user("agent_outputs", user_id, 10)
                     if o.get("section") == "recovery"],
    }


@app.get("/dashboard/matches")
def dashboard_matches(user_id: str):
    return {"matches": _by_user("match_results", user_id, 20)}


@app.get("/dashboard/training")
def dashboard_training(user_id: str):
    return {"sessions": _by_user("training_sessions", user_id, 20)}


@app.get("/dashboard/logistics")
def dashboard_logistics(user_id: str):
    return {"events": _by_user("calendar_events", user_id, 20)}


@app.get("/dashboard/sponsorship")
def dashboard_sponsorship(user_id: str):
    return {"opportunities": _by_user("sponsorship_opportunities", user_id, 20)}


# ── /chat : RAG-lite stand-in for the real Coaching/Chat agent ─────
# The real backend does RedisVL KNN retrieval (framework v4 §6b). This stub
# uses recency instead of vector search, then Claude for the grounded answer,
# so the agent layer's "ask" path is testable end-to-end without Redis.
class ChatIn(BaseModel):
    user_id: str
    question: str


@app.post("/chat")
def chat(body: ChatIn):
    entries = _by_user("entries", body.user_id, 15)
    if not entries:
        return {"answer": "I don't have any journal entries for you yet.", "sources": []}
    if not os.environ.get("ANTHROPIC_API_KEY"):
        joined = "; ".join(e["text"] for e in entries[:5])
        return {"answer": f"(no ANTHROPIC_API_KEY set) Recent entries: {joined}",
                "sources": [e["entry_id"] for e in entries[:5]]}
    import anthropic

    context = "\n\n".join(f"[{e['section'].upper()}] {e['text']}" for e in entries)
    prompt = (
        "You are a sports performance analyst reviewing an athlete's journal. "
        "Answer using ONLY the entries below. Be specific — quote what they wrote. "
        "If the entries lack enough information, say so.\n\n"
        f"JOURNAL ENTRIES:\n{context}\n\nQUESTION: {body.question}"
    )
    resp = anthropic.Anthropic().messages.create(
        model=os.environ.get("SYNTHESIS_MODEL", "claude-sonnet-4-6"),
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    answer = next((b.text for b in resp.content if b.type == "text"), "")
    return {"answer": answer, "sources": [e["entry_id"] for e in entries]}
