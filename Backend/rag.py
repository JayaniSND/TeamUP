"""RAG pipeline: embed → store (RedisVL) → retrieve → LangCache.

Three things this module does:

  1. embed(text)        — turns any text into a 384-float vector using a local
                          sentence-transformer model (no API key, runs on CPU).

  2. store_entry(...)   — called after every POST /entries; embeds the text and
                          writes the vector + metadata to RedisVL so it's
                          searchable later.

  3. retrieve(...)      — search at query time. "How has my serve been?"
                          returns RedisVL entry matches plus relevant Supabase
                          records across match/training/recovery/metrics/etc.

  4. cache_get/set(...)  — semantic response cache (LangCache-inspired). Before
                           calling Claude, check whether a semantically similar
                           question was already answered. Stores (question_embedding,
                           answer) in Redis. Avoids redundant Claude calls.

Everything is behind a single guard: if REDIS_URL is not set or reachable,
RedisVL silently no-ops and /chat falls back to Supabase database retrieval.
"""

from __future__ import annotations

import logging
import os
import re
import socket
import ssl
from typing import Optional
from urllib.parse import urlparse

import numpy as np

from database import supabase
from services.user_identity import resolve_user_id

log = logging.getLogger("rag")

REDIS_URL: str = os.environ.get("REDIS_URL", "").strip()
DIM: int = 384            # all-MiniLM-L6-v2 output dimension
INDEX_NAME: str = "entries_idx"
CACHE_INDEX_NAME: str = "chat_cache_idx"
CACHE_THRESHOLD: float = 0.15   # cosine distance below this = cache hit
REDIS_CONNECT_TIMEOUT: float = float(os.environ.get("REDIS_CONNECT_TIMEOUT", "0.5"))
REDIS_SOCKET_TIMEOUT: float = float(os.environ.get("REDIS_SOCKET_TIMEOUT", "0.5"))

_model = None          # sentence-transformer, loaded lazily on first embed call
_index = None          # RedisVL SearchIndex for journal entries
_cache_index = None    # RedisVL SearchIndex for LangCache
_redis_unreachable = False

_DB_TABLES = (
    "entries",
    "match_results",
    "training_sessions",
    "recovery_logs",
    "metrics",
    "calendar_events",
    "sponsorship_opportunities",
    "agent_outputs",
)

_TOKEN_ALIASES = {
    "opponet": "opponent",
    "opponentt": "opponent",
    "opponnent": "opponent",
    "played": "match",
    "play": "match",
}

_MATCH_ENTRY_SECTIONS = {"match_results"}
_MATCH_TEXT_RE = re.compile(
    r"\b(beat|defeated|lost to|played against|won\b.*\bagainst)\b"
    r"|(\b\d{1,2}-\d{1,2}\b.*\b(against|opponent|beat|lost|won)\b)"
    r"|(\b(against|opponent|beat|lost|won)\b.*\b\d{1,2}-\d{1,2}\b)",
    re.IGNORECASE,
)


def _tokens(text: str) -> set[str]:
    tokens = {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}
    expanded = set(tokens)
    for token in tokens:
        alias = _TOKEN_ALIASES.get(token)
        if alias:
            expanded.add(alias)
    return expanded


def _is_last_opponent_query(q_tokens: set[str]) -> bool:
    return bool({"last", "latest", "recent", "most"} & q_tokens and {"opponent", "match"} & q_tokens)


def _looks_like_match_entry(doc_section: str, text: str) -> bool:
    return doc_section in _MATCH_ENTRY_SECTIONS or bool(_MATCH_TEXT_RE.search(text or ""))


def _doc_score(table: str, doc_section: str, text: str, q_tokens: set[str]) -> int:
    overlap = len(q_tokens & _tokens(f"{doc_section} {text}"))
    score = overlap

    # History questions like "who was my last opponet" should land on the
    # structured match table, not whichever journal note happens to be newest.
    if table == "match_results" and {"opponent", "match"} & q_tokens:
        score += 2
    if table == "match_results" and {"last", "latest", "recent", "most"} & q_tokens:
        score += 1
    if table == "entries" and _is_last_opponent_query(q_tokens) and _looks_like_match_entry(doc_section, text):
        score += 3

    return score


def _row_time(row: dict) -> str:
    return str(row.get("date") or row.get("start_time") or row.get("created_at") or row.get("ts") or "")


def _time_rank(value: str) -> float:
    if not value:
        return 0.0
    try:
        from datetime import datetime

        return datetime.fromisoformat(str(value).replace("Z", "+00:00")[:25]).timestamp()
    except Exception:
        return 0.0


def _doc_text(table: str, row: dict) -> tuple[str, str]:
    if table == "entries":
        section = row.get("section") or "entry"
        text = row.get("text") or ""
        when = row.get("created_at") or row.get("ts")
        if when:
            text = f"Entry on {when}: {text}"
        return str(section), text
    if table == "match_results":
        return "match_results", (
            f"Match result on {row.get('date') or 'date unknown'}: opponent {row.get('opponent') or 'unknown'}, "
            f"event {row.get('event_name') or 'unknown'}, result {row.get('result') or 'unknown'}, "
            f"score {row.get('score') or 'unknown'}. Notes: {row.get('notes') or ''}"
        ).strip()
    if table == "training_sessions":
        return "training", (
            f"Training session on {row.get('date') or 'date unknown'}: {row.get('session_type') or 'session'}, "
            f"{row.get('duration_minutes') or '?'} minutes, intensity {row.get('intensity') or '?'}, "
            f"focus {row.get('focus_area') or 'unknown'}. Notes: {row.get('notes') or ''}"
        ).strip()
    if table == "recovery_logs":
        return "recovery", (
            f"Recovery log on {row.get('date') or 'date unknown'}: soreness {row.get('soreness_level')}, "
            f"fatigue {row.get('fatigue_level')}, sleep {row.get('sleep_hours')}, "
            f"area {row.get('injury_area') or 'none'}, risk {row.get('risk_level') or 'unknown'}. "
            f"Notes: {row.get('notes') or ''}"
        ).strip()
    if table == "metrics":
        return "metrics", (
            f"Metric on {row.get('date') or 'date unknown'}: {row.get('metric_name') or 'metric'} "
            f"= {row.get('metric_value')} {row.get('unit') or ''}"
        ).strip()
    if table == "calendar_events":
        return "logistics", (
            f"Calendar event {row.get('title') or 'event'}: type {row.get('event_type') or 'event'}, "
            f"starts {row.get('start_time') or 'unknown'}, ends {row.get('end_time') or 'unknown'}, "
            f"location {row.get('location') or 'unknown'}."
        ).strip()
    if table == "sponsorship_opportunities":
        return "sponsorship", (
            f"Sponsorship opportunity {row.get('brand_name') or 'brand'}: category {row.get('category') or 'unknown'}, "
            f"fit {row.get('fit_score')}, status {row.get('status') or 'unknown'}. "
            f"Reason: {row.get('reason') or ''}"
        ).strip()
    if table == "agent_outputs":
        return "agent_outputs", (
            f"{row.get('agent_name') or 'Agent'} output for {row.get('section') or 'section'}: "
            f"{row.get('summary') or ''} Recommended action: {row.get('recommended_action') or ''}"
        ).strip()
    return table, " ".join(str(v) for v in row.values() if v is not None)


def _fetch_user_rows(table: str, resolved_user_id: str, limit: int = 40) -> list[dict]:
    """Read recent rows for a user. We try likely timestamp columns in order so
    last/most-recent questions are based on actual row dates, not REST default
    ordering."""
    for order_col in ("date", "start_time", "created_at"):
        try:
            return (
                supabase.table(table)
                .select("*")
                .eq("user_id", resolved_user_id)
                .order(order_col, desc=True)
                .limit(limit)
                .execute()
                .data
                or []
            )
        except Exception:
            continue

    rows = (
        supabase.table(table)
        .select("*")
        .eq("user_id", resolved_user_id)
        .limit(limit)
        .execute()
        .data
        or []
    )
    rows.sort(key=lambda row: _time_rank(_row_time(row)), reverse=True)
    return rows


def retrieve_supabase(question: str, user_id: str, top_k: int = 8, section: Optional[str] = None) -> list[dict]:
    """Retrieve RAG documents directly from Supabase when RedisVL is empty or unavailable.

    Framework v5 keeps RAG grounded in the athlete database. RedisVL is the
    preferred semantic index, but Supabase remains the source of truth and gives
    us a deterministic fallback for demos/local development.
    """
    resolved_user_id = resolve_user_id(user_id)
    q_tokens = _tokens(question)
    docs: list[dict] = []

    for table in _DB_TABLES:
        try:
            rows = _fetch_user_rows(table, resolved_user_id, limit=40)
        except Exception as e:  # noqa: BLE001
            log.debug("Supabase RAG skip %s for %s: %s", table, resolved_user_id, e)
            continue

        for row in rows:
            doc_section, text = _doc_text(table, row)
            if section and doc_section != section and row.get("section") != section:
                continue
            if not text:
                continue
            score = _doc_score(table, doc_section, text, q_tokens)
            docs.append({
                "entry_id": str(row.get("id") or row.get("entry_id") or f"{table}:{len(docs)}"),
                "section": doc_section,
                "text": text,
                "score": -float(score),
                "source_table": table,
                "ts": _row_time(row),
            })

    if not docs:
        return []

    if _is_last_opponent_query(q_tokens):
        match_docs = [
            d for d in docs
            if (
                d.get("section") == "match_results"
                or _looks_like_match_entry(str(d.get("section") or ""), str(d.get("text") or ""))
            )
        ]
        if match_docs:
            match_docs.sort(key=lambda d: _time_rank(str(d.get("ts") or "")), reverse=True)
            return match_docs[:top_k]

    docs.sort(key=lambda d: (d["score"], -_time_rank(str(d.get("ts") or ""))))
    positive = [d for d in docs if float(d["score"]) < 0]
    return (positive or docs)[:top_k]


# ── Embedding ──────────────────────────────────────────────────────

def embed(text: str) -> list[float]:
    """Return a 384-float normalised embedding for any text string."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        log.info("Loading sentence-transformer model (first call only)…")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    vec: np.ndarray = _model.encode(text, normalize_embeddings=True)
    return vec.tolist()


# ── RedisVL index setup ────────────────────────────────────────────

def _redis_reachable() -> bool:
    """Cheap guard before RedisVL initializes. Some stale TLS Redis URLs can hang
    inside RedisVL/redis-py handshakes; this keeps chat on the Supabase fallback."""
    global _redis_unreachable
    if _redis_unreachable:
        return False
    if not REDIS_URL:
        return False

    try:
        parsed = urlparse(REDIS_URL)
        host = parsed.hostname
        port = parsed.port or (6380 if parsed.scheme == "rediss" else 6379)
        if not host:
            return False
        with socket.create_connection((host, port), timeout=REDIS_CONNECT_TIMEOUT) as sock:
            sock.settimeout(REDIS_SOCKET_TIMEOUT)
            if parsed.scheme == "rediss":
                context = ssl.create_default_context()
                with context.wrap_socket(sock, server_hostname=host):
                    return True
            return True
    except Exception as e:  # noqa: BLE001
        log.warning("Redis unreachable; RAG will use recency fallback: %s", e)
        _redis_unreachable = True
        return False

def _entry_index():
    """Return (and lazily create) the journal-entries vector index."""
    global _index
    if _index is not None:
        return _index
    if not _redis_reachable():
        return None

    try:
        from redisvl.index import SearchIndex

        schema = {
            "index": {
                "name": INDEX_NAME,
                "prefix": "entry",
                "storage_type": "hash",
            },
            "fields": [
                {"name": "entry_id",  "type": "tag"},
                {"name": "user_id",   "type": "tag"},
                {"name": "section",   "type": "tag"},
                {"name": "text",      "type": "text"},
                {
                    "name": "embedding",
                    "type": "vector",
                    "attrs": {
                        "dims": DIM,
                        "distance_metric": "cosine",
                        "algorithm": "flat",
                        "datatype": "float32",
                    },
                },
            ],
        }
        idx = SearchIndex.from_dict(
            schema,
            redis_url=REDIS_URL,
            socket_connect_timeout=REDIS_CONNECT_TIMEOUT,
            socket_timeout=REDIS_SOCKET_TIMEOUT,
        )
        idx.create(overwrite=False)
        _index = idx
        log.info("RedisVL entries index ready (%s)", INDEX_NAME)
    except Exception as e:
        log.warning("RedisVL entries index unavailable: %s", e)
        _index = None

    return _index


def _cache_idx():
    """Return (and lazily create) the LangCache vector index."""
    global _cache_index
    if _cache_index is not None:
        return _cache_index
    if not _redis_reachable():
        return None

    try:
        from redisvl.index import SearchIndex

        schema = {
            "index": {
                "name": CACHE_INDEX_NAME,
                "prefix": "cache",
                "storage_type": "hash",
            },
            "fields": [
                {"name": "user_id",   "type": "tag"},
                {"name": "question",  "type": "text"},
                {"name": "answer",    "type": "text"},
                {
                    "name": "embedding",
                    "type": "vector",
                    "attrs": {
                        "dims": DIM,
                        "distance_metric": "cosine",
                        "algorithm": "flat",
                        "datatype": "float32",
                    },
                },
            ],
        }
        idx = SearchIndex.from_dict(
            schema,
            redis_url=REDIS_URL,
            socket_connect_timeout=REDIS_CONNECT_TIMEOUT,
            socket_timeout=REDIS_SOCKET_TIMEOUT,
        )
        idx.create(overwrite=False)
        _cache_index = idx
        log.info("RedisVL cache index ready (%s)", CACHE_INDEX_NAME)
    except Exception as e:
        log.warning("RedisVL cache index unavailable: %s", e)
        _cache_index = None

    return _cache_index


# ── Store ──────────────────────────────────────────────────────────

def store_entry(entry_id: str, user_id: str, section: str, text: str) -> bool:
    """Embed a journal entry and write it to RedisVL.

    Called automatically inside POST /entries and POST /ingest (after the
    Supabase write succeeds). Returns True on success, False if Redis is
    unavailable or the embed fails.
    """
    idx = _entry_index()
    if idx is None:
        return False

    try:
        resolved_user_id = resolve_user_id(user_id)
        vec = np.array(embed(text), dtype=np.float32)
        idx.load([{
            "entry_id":  str(entry_id),
            "user_id":   str(resolved_user_id),
            "section":   str(section),
            "text":      text,
            "embedding": vec.tobytes(),
        }], id_field="entry_id")
        return True
    except Exception as e:
        log.warning("store_entry failed for %s: %s", entry_id, e)
        return False


# ── Retrieve ───────────────────────────────────────────────────────

def retrieve(
    question: str,
    user_id: str,
    top_k: int = 8,
    section: Optional[str] = None,
) -> list[dict]:
    """Search over this athlete's RAG corpus.

    RedisVL handles embedded entries when available. Supabase structured records
    are also searched so history questions can draw from match_results, metrics,
    recovery logs, calendar events, and agent outputs.

    Returns up to top_k docs with entry_id, section, text, score, source_table.
    """
    redis_docs: list[dict] = []
    idx = _entry_index()

    if idx is not None:
        try:
            from redisvl.query import VectorQuery
            from redisvl.query.filter import Tag

            q_vec = np.array(embed(question), dtype=np.float32).tolist()

            resolved_user_id = resolve_user_id(user_id)
            user_filter = Tag("user_id") == resolved_user_id
            if section:
                f = user_filter & (Tag("section") == section)
            else:
                f = user_filter

            query = VectorQuery(
                vector=q_vec,
                vector_field_name="embedding",
                return_fields=["entry_id", "text", "section", "user_id"],
                filter_expression=f,
                num_results=top_k,
            )
            results = idx.query(query)
            redis_docs = [
                {
                    "entry_id": r.get("entry_id"),
                    "section":  r.get("section"),
                    "text":     r.get("text"),
                    "score":    r.get("vector_distance"),
                    "source_table": "entries",
                }
                for r in results
            ]
        except Exception as e:
            log.warning("retrieve failed: %s", e)

    db_docs = retrieve_supabase(question, user_id, top_k=top_k, section=section)
    db_relevant = [d for d in db_docs if float(d.get("score") or 0) < 0]
    combined = [*db_relevant, *redis_docs] if redis_docs else db_docs

    seen: set[tuple[str, str]] = set()
    deduped: list[dict] = []
    for doc in combined:
        key = (str(doc.get("source_table") or "entries"), str(doc.get("entry_id") or ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(doc)
    return deduped[:top_k]


# ── LangCache ──────────────────────────────────────────────────────
# Before calling Claude for /chat, check if a semantically similar question
# was already answered (cosine distance < CACHE_THRESHOLD). If yes, return
# the cached answer — no Claude call needed.

def cache_get(question: str, user_id: str) -> Optional[str]:
    """Return a cached Claude answer if one exists for a similar question."""
    idx = _cache_idx()
    if idx is None:
        return None

    try:
        from redisvl.query import VectorQuery
        from redisvl.query.filter import Tag

        resolved_user_id = resolve_user_id(user_id)
        q_vec = np.array(embed(question), dtype=np.float32).tolist()
        query = VectorQuery(
            vector=q_vec,
            vector_field_name="embedding",
            return_fields=["answer", "question"],
            filter_expression=Tag("user_id") == resolved_user_id,
            num_results=1,
        )
        results = idx.query(query)
        if results:
            dist = float(results[0].get("vector_distance", 1.0))
            if dist < CACHE_THRESHOLD:
                log.info("LangCache hit (dist=%.3f): %s", dist, question[:60])
                return results[0].get("answer")
    except Exception as e:
        log.warning("cache_get failed: %s", e)

    return None


def cache_set(question: str, user_id: str, answer: str) -> None:
    """Store a (question, answer) pair in the LangCache index."""
    idx = _cache_idx()
    if idx is None:
        return

    try:
        resolved_user_id = resolve_user_id(user_id)
        key = f"{resolved_user_id}:{hash(question) & 0xFFFFFFFF}"
        vec = np.array(embed(question), dtype=np.float32)
        idx.load([{
            "user_id":   resolved_user_id,
            "question":  question,
            "answer":    answer,
            "embedding": vec.tobytes(),
        }], keys=[key])
    except Exception as e:
        log.warning("cache_set failed: %s", e)


# ── Backfill helper ────────────────────────────────────────────────

def backfill_entries(entries: list[dict]) -> int:
    """Embed and store a batch of existing entries that weren't vectorised yet.

    Used by POST /admin/backfill to bring RedisVL in sync after the Supabase
    tables were seeded without the embed step running.

    entries: list of dicts with entry_id, user_id, section, text keys.
    Returns the number of entries successfully stored.
    """
    ok = 0
    for e in entries:
        if store_entry(e.get("entry_id", ""), e.get("user_id", ""),
                       e.get("section", ""), e.get("text", "")):
            ok += 1
    return ok
