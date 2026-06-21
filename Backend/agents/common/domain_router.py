"""Deterministic domain pre-router for the Orchestrator.

The Claude intent classifier (agents/common/claude.classify_intent) is the primary
router, but it is conservative — it prefers the generic `ask` route when unsure, so
phrasings like "summarize my recent performance" never reach the Performance agent,
and a bare greeting dead-ends at the Librarian.

This module adds a fast, dependency-free keyword layer the orchestrator runs ALONGSIDE
Claude so that:

  • broad, fuzzy keyword matches reliably trigger the right specialist
    (e.g. "sore", "tired", "knee" → recovery; "flight", "hotel", "trip" → logistics),
  • a message that touches several domains lights up SEVERAL specialists,
  • small-talk / generic messages ("hi", "thanks", "ok") still get a real,
    friendly agent call instead of an empty Librarian filing.

It only ever returns the four specialists the orchestrator's `_route_action` already
handles — recovery, performance, logistics, sponsorship — so nothing here can route
to an unwired agent. Lead selection and multi-agent fan-out live in the orchestrator;
this module just answers "which domains does this message touch?".
"""

from __future__ import annotations

import re

# Specialist domains, in the priority order used when picking a lead from keywords
# alone (physical wellbeing first, then form, then travel, then commercial).
DOMAIN_PRIORITY = ("recovery", "performance", "logistics", "sponsorship")

# Broad / fuzzy keyword sets. Matching is substring-on-word-boundaries so stems hit
# their variants ("sore" → "soreness", "perform" → "performing") without matching
# unrelated words. Keep these generous — the goal is HIGH recall: more messages
# should trigger a specialist, and a false-positive only adds a short supporting
# note, never a wrong primary answer.
_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "recovery": (
        "tired", "exhausted", "fatigue", "fatigued", "sore", "soreness", "ache",
        "aching", "pain", "painful", "hurt", "hurts", "injury", "injured", "strain",
        "strained", "recovery", "recover", "recovering", "rest", "rested", "resting",
        "sleep", "slept", "sleepy", "stress", "stressed", "burnout", "burned out",
        "overtrain", "overtrained", "overtraining", "knee", "shoulder", "wrist",
        "ankle", "elbow", "hamstring", "back pain", "feel bad", "feeling bad",
        "not feeling", "drained", "wiped", "stiff", "cramp", "cramping",
    ),
    "performance": (
        "performance", "perform", "performing", "stats", "statistic", "progress",
        "trend", "trending", "form", "improve", "improving", "improvement", "win",
        "wins", "winning", "won", "loss", "losses", "losing", "lost", "result",
        "results", "score", "scoring", "level up", "getting better", "getting worse",
        "how am i doing", "how am i performing", "playing well", "playing better",
        "weakness", "weakest", "strongest", "strength",
    ),
    "logistics": (
        "flight", "flights", "fly", "flying", "plane", "airfare", "airport",
        "travel", "traveling", "travelling", "trip", "go there", "get there",
        "hotel", "hotels", "stay", "staying", "accommodation", "lodging", "room",
        "booking", "book a", "book my", "book the", "book flight", "book hotel",
        "tournament", "away match", "away game", "drive to", "commute", "transport",
        "check-in", "check in", "checkout", "pack", "packing",
    ),
    "sponsorship": (
        "sponsor", "sponsors", "sponsorship", "brand", "brands", "deal", "deals",
        "endorsement", "endorse", "outreach", "partnership", "partner with",
        "draft email", "draft an email", "sponsor fit", "marketing",
    ),
}

# Small-talk / acknowledgements. When a SHORT message is one of these (and has no
# domain keyword), route it to the general athlete-care agent rather than the
# Librarian, so greetings still produce a real, friendly agent call.
_SMALLTALK_EXACT = frozenset({
    "hi", "hii", "hiya", "hey", "heya", "hello", "yo", "sup", "wassup", "howdy",
    "thanks", "thank you", "thank u", "thx", "ty", "tysm", "cheers", "ok", "okay",
    "k", "kk", "cool", "nice", "great", "awesome", "perfect", "got it", "gotcha",
    "good morning", "good afternoon", "good evening", "gm", "ge", "morning",
    "yes", "yep", "yeah", "no", "nope", "lol", "haha", "bye", "goodbye", "cya",
    "see you", "good night", "gn", "np", "no problem", "sounds good",
})

_SMALLTALK_PREFIXES = (
    "hi ", "hey ", "hello ", "thanks ", "thank you ", "good morning",
    "good afternoon", "good evening",
)

_WORD_RE = re.compile(r"[a-z]+")


def _normalize(message: str) -> str:
    return " ".join((message or "").lower().split())


def _keyword_hit(keyword: str, tokens: list[str]) -> bool:
    """Token-aware match — broad enough for stems, tight enough to avoid bleed.

    • Single-word keyword → prefix-match on a whole token, so stems still hit their
      variants ("book" → "booking", "perform" → "performing") without matching
      across word boundaries.
    • Multi-word keyword → the keyword's tokens must appear as a consecutive run, so
      "check in" matches "check in" but NOT "check injury".
    This is what stops the old substring matcher from flagging logistics on
    "check INjury".
    """
    kw_tokens = _WORD_RE.findall(keyword)
    if not kw_tokens:
        return False
    if len(kw_tokens) == 1:
        kw = kw_tokens[0]
        return any(tok.startswith(kw) for tok in tokens)
    n = len(kw_tokens)
    return any(tokens[i : i + n] == kw_tokens for i in range(len(tokens) - n + 1))


def detect_domains(message: str) -> list[str]:
    """Return the specialist domains a message touches, in priority order.

    Token-aware keyword matching keeps it broad/fuzzy (stems hit their variants)
    without bleeding across word boundaries. Returns a de-duplicated list ordered by
    DOMAIN_PRIORITY; empty when no domain keyword hits.
    """
    tokens = _WORD_RE.findall(_normalize(message))
    if not tokens:
        return []
    return [
        domain
        for domain in DOMAIN_PRIORITY
        if any(_keyword_hit(kw, tokens) for kw in _DOMAIN_KEYWORDS[domain])
    ]


def predict_agents(message: str) -> list[str]:
    """Best-effort guess, from the message ALONE, of which agents the orchestrator
    will use — computed instantly (no LLM, no IO) so the Live Agent graph can render
    the planned network BEFORE the real calls run. The authoritative trace refines
    this as agents actually fire.

    Always includes `athlete_context` (loaded for every message). Mirrors the
    orchestrator's routing: small-talk / no-domain → assistant; otherwise the lead
    specialist plus up to two supporting analysis specialists.
    """
    planned = ["athlete_context"]
    if is_smalltalk(message):
        return planned + ["assistant"]
    domains = detect_domains(message)
    if not domains:
        return planned + ["assistant"]
    lead = domains[0]
    planned.append(lead)
    for extra in domains[1:]:
        if extra in ("recovery", "performance") and extra not in planned:
            planned.append(extra)
    return planned


def is_smalltalk(message: str) -> bool:
    """True for greetings / thanks / short acknowledgements with no domain content.

    Guarded so genuine questions never count as small-talk: any domain keyword, a
    question mark, or more than three words disqualifies it.
    """
    text = _normalize(message).strip(" !.")
    if not text:
        return True  # empty / whitespace — treat as a harmless greeting
    if "?" in message:
        return False
    if detect_domains(message):
        return False
    if text in _SMALLTALK_EXACT:
        return True
    words = _WORD_RE.findall(text)
    if len(words) > 3:
        return False
    if text.startswith(_SMALLTALK_PREFIXES):
        return True
    # A 1-2 word message whose words are all acknowledgement tokens.
    return bool(words) and all(w in _SMALLTALK_EXACT for w in words)
