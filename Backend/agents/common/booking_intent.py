"""Deterministic booking intent parsing shared by orchestrators.

The top-level intent router decides whether a message belongs to Logistics.
This helper handles the narrower question Logistics needs answered: which
booking category did the user actually ask to see?
"""

from __future__ import annotations

import re

BookingIntent = str

BOOKING_INTENTS: tuple[BookingIntent, ...] = (
    "flight_only",
    "hotel_only",
    "flight_hotel",
    "fee_only",
    "general",
)

_FLIGHT_PATTERNS = (
    r"\bbook(?:\s+(?:a|my))?\s+flights?\b",
    r"\bfind(?:\s+(?:me|a|my))*\s+flights?\b",
    r"\bflights?\s+(?:to|for)\s+(?:the\s+)?match\b",
    r"\bplane\s+tickets?\b",
    r"\bairfare\b",
    r"\bflight\s+booking\b",
)

_HOTEL_PATTERNS = (
    r"\bbook(?:\s+(?:a|my))?\s+hotels?\b",
    r"\bfind(?:\s+(?:me|a|my))*\s+hotels?\b",
    r"\bstay\s+near\s+(?:the\s+)?(?:match|event|tournament)\b",
    r"\baccommodations?\b",
    r"\brooms?\b",
    r"\bhotel\s+booking\b",
)

_FLIGHT_HOTEL_PATTERNS = (
    r"\bbook(?:\s+(?:a|my))?\s+flights?\s+(?:and|&|\+)\s+hotels?\b",
    r"\bbook(?:\s+(?:a|my))?\s+hotels?\s+(?:and|&|\+)\s+flights?\b",
    r"\bfind\s+travel\s+packages?\b",
    r"\bplan\s+(?:the|my|this)?\s*trip\b",
    r"\bplan\s+(?:my\s+)?travel\b",
    r"\btravel\s+(?:and|&|\+)\s+stay\b",
)

_FEE_PATTERNS = (
    r"\bhow\s+much\s+(?:is|are)\s+the\s+fees?\b",
    r"\bshow\s+(?:me\s+)?(?:the\s+)?fees?\b",
    r"\bpayment\s+fees?\b",
    r"\bservice\s+fees?\b",
)


def _matches(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def classify_booking_intent(message: str | None, fallback: BookingIntent | None = None) -> BookingIntent:
    """Return the explicit booking category requested by the user."""
    text = re.sub(r"\s+", " ", str(message or "").lower()).strip()
    if not text:
        return fallback if fallback in BOOKING_INTENTS else "general"

    has_flight = _matches(text, _FLIGHT_PATTERNS)
    has_hotel = _matches(text, _HOTEL_PATTERNS)

    if _matches(text, _FLIGHT_HOTEL_PATTERNS) or (has_flight and has_hotel):
        return "flight_hotel"
    if _matches(text, _FEE_PATTERNS):
        return "fee_only"
    if has_flight:
        return "flight_only"
    if has_hotel:
        return "hotel_only"
    return fallback if fallback in BOOKING_INTENTS else "general"


def booking_kinds_for_intent(intent: BookingIntent) -> list[str]:
    """Map booking intent to representative option kinds."""
    if intent == "flight_only":
        return ["flight"]
    if intent == "hotel_only":
        return ["hotel"]
    if intent == "flight_hotel":
        return ["flight", "hotel"]
    if intent == "fee_only":
        return []
    return ["flight", "hotel"]


def option_allowed_for_intent(kind: str | None, intent: BookingIntent) -> bool:
    if intent == "general":
        return True
    return str(kind or "") in set(booking_kinds_for_intent(intent))
