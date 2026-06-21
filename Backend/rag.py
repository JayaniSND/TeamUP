"""RAG pipeline: embed → store (RedisVL) → retrieve → LangCache.

Three things this module does:

  1. embed(text)        — turns any text into a 384-float vector using a local
                          sentence-transformer model (no API key, runs on CPU).

  2. store_entry(...)   — called after every POST /entries; embeds the text and
                          writes the vector + metadata to RedisVL so it's
                          searchable later.

  3. retrieve(...)      — KNN search at query time. "How has my serve been?"
                          returns the 8 journal entries whose *meaning* is closest
                          to that question, regardless of exact word overlap.

  4. cache_get/set(...)  — semantic response cache (LangCache-inspired). Before
                           calling Claude, check whether a semantically similar
                           question was already answered. Stores (question_embedding,
                           answer) in Redis. Avoids redundant Claude calls.

Everything is behind a single guard: if REDIS_URL is not set, all four
functions silently no-op and /chat falls back to recency retrieval in main.py.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import numpy as np

log = logging.getLogger("rag")

REDIS_URL: str = os.environ.get("REDIS_URL", "").strip()
DIM: int = 384            # all-MiniLM-L6-v2 output dimension
INDEX_NAME: str = "entries_idx"
CACHE_INDEX_NAME: str = "chat_cache_idx"
CACHE_THRESHOLD: float = 0.15   # cosine distance below this = cache hit

_model = None          # sentence-transformer, loaded lazily on first embed call
_index = None          # RedisVL SearchIndex for journal entries
_cache_index = None    # RedisVL SearchIndex for LangCache


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

def _entry_index():
    """Return (and lazily create) the journal-entries vector index."""
    global _index
    if _index is not None:
        return _index
    if not REDIS_URL:
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
        idx = SearchIndex.from_dict(schema, redis_url=REDIS_URL)
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
    if not REDIS_URL:
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
        idx = SearchIndex.from_dict(schema, redis_url=REDIS_URL)
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
        vec = np.array(embed(text), dtype=np.float32)
        idx.load([{
            "entry_id":  str(entry_id),
            "user_id":   str(user_id),
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
    """KNN search over this athlete's journal entries.

    Returns up to top_k entries sorted by semantic similarity to `question`.
    Each result is a dict with entry_id, section, text, score.

    If Redis is unavailable, returns an empty list (caller falls back to
    recency retrieval).
    """
    idx = _entry_index()
    if idx is None:
        return []

    try:
        from redisvl.query import VectorQuery
        from redisvl.query.filter import Tag

        q_vec = np.array(embed(question), dtype=np.float32).tolist()

        user_filter = Tag("user_id") == user_id
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
        return [
            {
                "entry_id": r.get("entry_id"),
                "section":  r.get("section"),
                "text":     r.get("text"),
                "score":    r.get("vector_distance"),
            }
            for r in results
        ]
    except Exception as e:
        log.warning("retrieve failed: %s", e)
        return []


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

        q_vec = np.array(embed(question), dtype=np.float32).tolist()
        query = VectorQuery(
            vector=q_vec,
            vector_field_name="embedding",
            return_fields=["answer", "question"],
            filter_expression=Tag("user_id") == user_id,
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
        key = f"{user_id}:{hash(question) & 0xFFFFFFFF}"
        vec = np.array(embed(question), dtype=np.float32)
        idx.load([{
            "user_id":   user_id,
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
