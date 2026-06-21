"""Travel booking + Stripe Checkout (test mode) for the demo.

Flow (athlete-care travel → real, safe checkout):
  1. representative_options(ctx)  — build priced flight / hotel / entry-fee options
     from the athlete's REAL calendar (no live inventory API; the *payment* is the
     real part of the demo, per product decision).
  2. create_checkout_session()   — record a `bookings` row (pending_payment) and
     open a Stripe **test-mode** Checkout Session. The athlete pays on Stripe's
     hosted page with a test card (4242 4242 4242 4242) — no real money moves.
  3. confirm_checkout()          — on return, verify the session with Stripe and
     mark the booking `paid`.

Safety: nothing is charged without the athlete completing Stripe's hosted
checkout themselves (that click IS the explicit confirmation). Test keys mean no
real charge. To go live you'd swap STRIPE_SECRET_KEY for a live key — gate that
behind real consent. Without a key, checkout degrades to a clear "not configured"
message rather than faking a payment.

Env:
  STRIPE_SECRET_KEY   sk_test_…  (required to enable checkout; safe to omit)
  FRONTEND_URL        where Stripe redirects back (default http://localhost:5173)
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta

from database import supabase
from services import agent_event_tracker as tracker

log = logging.getLogger("booking_service")

# Stripe is optional: import defensively so the backend boots without the package.
try:
    import stripe
except Exception:  # noqa: BLE001
    stripe = None

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "").strip()
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173").rstrip("/")

# Representative pricing (minor units / cents). Tweak freely — this is demo pricing.
_HOTEL_NIGHTLY_CENTS = 12900
_HOTEL_NIGHTS = 3
_FLIGHT_CENTS = 24500
_ENTRY_CENTS = 6500
_SERVICE_FEE_CENTS = 0

_KINDS = ("hotel", "flight", "tournament_entry")


def stripe_configured() -> bool:
    return bool(stripe and STRIPE_SECRET_KEY)


# ── representative options from the athlete's real schedule ─────────────────

def _parse_date(value) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if "T" in text:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _weekday(value: date) -> str:
    return value.strftime("%A")


def _event_date(event: dict | None) -> date | None:
    if not event:
        return None
    return (
        _parse_date(event.get("startDate"))
        or _parse_date(event.get("start_date"))
        or _parse_date(event.get("start_time"))
        or _parse_date(event.get("date"))
    )


def _event_type(event: dict | None) -> str:
    if not event:
        return ""
    return str(event.get("type") or event.get("event_type") or "").lower()


def _choose_trip(ctx: dict) -> dict | None:
    trips = list((ctx.get("travel") or {}).get("trips") or [])
    frontend_calendar = ctx.get("_frontend_calendar") or {}
    current_match = frontend_calendar.get("currentMatch") or frontend_calendar.get("current_match")
    if isinstance(current_match, dict):
        trips.insert(0, current_match)

    today = date.today()

    def sort_key(event: dict):
        event_date = _event_date(event)
        is_match = _event_type(event) == "match"
        future_rank = 0 if event_date and event_date >= today else 1
        return (future_rank, event_date or date.max, 0 if is_match else 1)

    valid_trips = [trip for trip in trips if isinstance(trip, dict)]
    return sorted(valid_trips, key=sort_key)[0] if valid_trips else None


def travel_plan_from_context(ctx: dict) -> dict:
    """Plan travel around the next match/tournament. Frontend session calendar
    data is runtime-only but still valid before persistence exists."""
    trip = _choose_trip(ctx)
    match_date = _event_date(trip)
    raw_location = ((trip or {}).get("location") or "").strip()
    location = raw_location if raw_location.lower() not in {"", "tbd", "unknown"} else "Match Location"
    event = (trip or {}).get("title") or "your next match"

    if not match_date:
        return {
            "trip": trip,
            "event": event,
            "location": location,
            "match_date": None,
            "travel_date": None,
            "return_date": None,
            "hotel_nights": _HOTEL_NIGHTS,
            "assumption": "",
        }

    travel_date = match_date - timedelta(days=1)
    return_date = match_date + timedelta(days=1)
    hotel_nights = max((return_date - travel_date).days, 1)
    return {
        "trip": trip,
        "event": event,
        "location": location,
        "match_date": match_date,
        "travel_date": travel_date,
        "return_date": return_date,
        "hotel_nights": hotel_nights,
        "assumption": (
            f"Since your match is on {_weekday(match_date)}, I'm looking for travel "
            f"and hotel options starting {_weekday(travel_date)}."
        ),
    }


def representative_options(ctx: dict, kinds: list[str] | None = None) -> list[dict]:
    """Priced, bookable options for the athlete's next trip. Synthesized from the
    real calendar (location/event) — these are representative, not live inventory."""
    kinds = kinds or list(_KINDS)
    plan = travel_plan_from_context(ctx)
    location = plan["location"]
    event = plan["event"]
    match_date = plan["match_date"]
    travel_date = plan["travel_date"]
    return_date = plan["return_date"]
    hotel_nights = plan["hotel_nights"]

    options: list[dict] = []
    if "flight" in kinds:
        options.append({
            "kind": "flight",
            "title": f"Flight to {location}",
            "location": location,
            "amount_cents": _FLIGHT_CENTS,
            "currency": "usd",
            "route": f"Home airport to {location}",
            "airline": "SportsMom Air",
            "description": (
                f"Depart {travel_date.isoformat()} and return {return_date.isoformat()} for {event}."
                if travel_date and return_date
                else "Economy, refundable — timed to the event window."
            ),
            "start_date": travel_date.isoformat() if travel_date else None,
            "start_time": "8:00 AM" if travel_date else None,
            "end_date": travel_date.isoformat() if travel_date else None,
            "end_time": "11:00 AM" if travel_date else None,
            "provider": "SportsMom Travel",
        })
    if "hotel" in kinds:
        options.append({
            "kind": "hotel",
            "title": f"Hotel near {location} · {hotel_nights} nights",
            "location": location,
            "amount_cents": _HOTEL_NIGHTLY_CENTS * hotel_nights,
            "currency": "usd",
            "description": (
                f"Check in {travel_date.isoformat()}, check out {return_date.isoformat()} for {event}."
                if travel_date and return_date
                else f"Walkable to the venue for {event}."
            ),
            "start_date": travel_date.isoformat() if travel_date else None,
            "start_time": "3:00 PM" if travel_date else None,
            "end_date": return_date.isoformat() if return_date else None,
            "end_time": "11:00 AM" if return_date else None,
            "provider": "SportsMom Hotel",
        })
    if "tournament_entry" in kinds:
        options.append({
            "kind": "tournament_entry",
            "title": f"{event} — entry fee",
            "location": location,
            "amount_cents": _ENTRY_CENTS,
            "currency": "usd",
            "description": "Singles main-draw entry.",
            "start_date": match_date.isoformat() if match_date else None,
            "start_time": "10:00 AM" if match_date else None,
            "end_date": match_date.isoformat() if match_date else None,
            "end_time": "12:00 PM" if match_date else None,
            "provider": "Tournament Desk",
        })
    return options


def representative_fee_summary(ctx: dict) -> dict:
    """Current fee-only summary. No travel searches are needed for this path."""
    option = representative_options(ctx, ["tournament_entry"])[0]
    base_price = int(option.get("amount_cents") or _ENTRY_CENTS)
    service_fee = _SERVICE_FEE_CENTS
    return {
        "base_price_cents": base_price,
        "service_fee_cents": service_fee,
        "total_cents": base_price + service_fee,
        "currency": option.get("currency") or "usd",
    }


# ── Stripe Checkout (test mode) ─────────────────────────────────────────────

def _with_trace(response: dict, tr: tracker.AgentEventTracker) -> dict:
    response["agent_trace"] = tr.get_trace()
    response["agentTrace"] = response["agent_trace"]
    response["flowId"] = tr.flow_id
    response["messageId"] = tr.message_id
    return response


def create_checkout_session(
    user_id: str,
    option: dict,
    flow_id: str | None = None,
    message_id: str | None = None,
) -> dict:
    tr = tracker.start_flow(user_id, message_id=message_id, flow_id=flow_id)
    tracker.request_received("Payment session requested")
    tracker.payment_session_started("Payment session creation started")
    try:
        response = tracker.track_agent_call_sync(
            from_agent="logistics",
            to_agent="payment",
            step="Creating Stripe checkout session",
            call=lambda: _create_checkout_session(user_id, option),
            bookingKind=str(option.get("kind") or "booking"),
        )
        tracker.payment_session_completed(
            "Payment session creation completed",
            ok=bool(response.get("ok")),
            configured=bool(response.get("configured", True)),
        )
        return _with_trace(response, tr)
    finally:
        tracker.clear_flow(tr)


def _create_checkout_session(user_id: str, option: dict) -> dict:
    """Record a pending booking and open a Stripe test Checkout Session.
    Returns {ok, checkout_url, booking_id, session_id} or a clear error."""
    amount = int(option.get("amount_cents") or 0)
    title = (option.get("title") or "Booking").strip()
    kind = option.get("kind") or "booking"
    currency = (option.get("currency") or "usd").lower()
    if amount <= 0:
        return {"ok": False, "error": "Invalid booking amount."}

    booking_id = _insert_booking(user_id, option, status="pending_payment", provider="stripe_test")

    if not stripe_configured():
        # Keys not set yet — don't fake a payment; tell the user what's missing.
        if booking_id:
            _update_booking(booking_id, {"status": "planned"})
        return {
            "ok": False,
            "configured": False,
            "booking_id": booking_id,
            "error": "Payments aren't enabled yet — add STRIPE_SECRET_KEY (sk_test_…) "
            "to Backend/.env to turn on Stripe test checkout.",
        }

    stripe.api_key = STRIPE_SECRET_KEY
    try:
        metadata = {"user_id": user_id, "kind": kind}
        if booking_id:
            metadata["booking_id"] = str(booking_id)
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": currency,
                    "product_data": {"name": title, "description": option.get("description") or kind},
                    "unit_amount": amount,
                },
                "quantity": 1,
            }],
            success_url=f"{FRONTEND_URL}/checkout/complete?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/checkout/cancelled",
            metadata=metadata,
            client_reference_id=str(booking_id) if booking_id else None,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("stripe checkout create failed: %s", e)
        if booking_id:
            _update_booking(booking_id, {"status": "failed"})
        return {"ok": False, "error": f"Could not start checkout: {e}"}

    if booking_id:
        _update_booking(booking_id, {"provider_ref": session.id})
    return {
        "ok": True,
        "configured": True,
        "booking_id": booking_id,
        "checkout_url": session.url,
        "session_id": session.id,
    }


def _to_plain_dict(value) -> dict:
    """Coerce a Stripe object (or anything) to a plain dict.

    stripe>=15 `StripeObject` is NOT a dict subclass and has no `.get` — calling
    `.get()` on `session.metadata` raises AttributeError (and a 500 that loses its
    CORS header, surfacing in the UI as a misleading 'could not reach' error).
    `.to_dict()` returns a plain mapping; fall back gracefully otherwise."""
    if isinstance(value, dict):
        return value
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return to_dict()
        except Exception:  # noqa: BLE001
            return {}
    return {}


def confirm_checkout(session_id: str) -> dict:
    """Verify a returned Checkout Session with Stripe and mark the booking paid."""
    tr = tracker.start_flow("demo-athlete", session_id=session_id)
    tracker.request_received("Payment return received")
    if not stripe_configured():
        tracker.agent_error("payment", "Stripe is not configured")
        tracker.final_response_started("Preparing payment status")
        tracker.final_response("Payment verification response sent")
        response = _with_trace({"ok": False, "configured": False, "error": "Stripe is not configured."}, tr)
        tracker.clear_flow(tr)
        return response
    try:
        stripe.api_key = STRIPE_SECRET_KEY
        try:
            session = tracker.track_agent_call_sync(
                from_agent="orchestrator",
                to_agent="payment",
                step="Verifying Stripe payment",
                call=lambda: stripe.checkout.Session.retrieve(session_id),
            )
        except Exception as e:  # noqa: BLE001
            log.warning("stripe session retrieve failed: %s", e)
            tracker.final_response_started("Preparing payment status")
            tracker.final_response("Payment verification response sent")
            return _with_trace({
                "ok": False,
                "error": f"Could not verify payment: {e}",
            }, tr)

        payment_status = getattr(session, "payment_status", None)
        paid = payment_status == "paid"
        metadata = _to_plain_dict(getattr(session, "metadata", None))
        booking_id = metadata.get("booking_id")
        tracker.payment_verified("Payment success verified" if paid else "Payment not completed", paid=paid)
        if booking_id:
            _update_booking(booking_id, {"status": "paid" if paid else "pending_payment"})
        booking = _get_booking(booking_id) if booking_id else None
        calendar_event = None
        if paid and booking:
            calendar_event = tracker.track_agent_call_sync(
                from_agent="payment",
                to_agent="calendar",
                step="Creating calendar event after payment",
                call=lambda: _booking_to_calendar_event(booking),
            )
            tracker.calendar_event_created("Calendar event created after payment")
        tracker.final_response_started("Preparing payment confirmation")
        tracker.final_response("Payment confirmation sent")
        return _with_trace({
            "ok": True,
            "paid": paid,
            "status": payment_status,
            "booking_id": booking_id,
            "booking": booking,
            "calendar_event": calendar_event,
        }, tr)
    finally:
        tracker.clear_flow(tr)


def list_bookings(user_id: str, limit: int = 20) -> list[dict]:
    try:
        res = (
            supabase.table("bookings").select("*").eq("user_id", user_id)
            .order("created_at", desc=True).limit(limit).execute()
        )
        return res.data or []
    except Exception as e:  # noqa: BLE001
        log.warning("list bookings failed: %s", e)
        return []


# ── Supabase writes (bookings table — see Backend/schema.sql) ────────────────

def _insert_booking(user_id: str, option: dict, status: str, provider: str):
    try:
        res = supabase.table("bookings").insert({
            "user_id": user_id,
            "kind": option.get("kind"),
            "title": option.get("title"),
            "location": option.get("location"),
            "amount_cents": int(option.get("amount_cents") or 0),
            "currency": (option.get("currency") or "usd").lower(),
            "status": status,
            "provider": provider,
            "metadata": {
                "description": option.get("description", ""),
                "start_date": option.get("start_date"),
                "start_time": option.get("start_time"),
                "end_date": option.get("end_date"),
                "end_time": option.get("end_time"),
                "provider": option.get("provider"),
            },
        }).execute()
        return (res.data or [{}])[0].get("id")
    except Exception as e:  # noqa: BLE001
        log.warning("insert booking failed: %s", e)
        return None


def _get_booking(booking_id) -> dict | None:
    if not booking_id:
        return None
    try:
        res = supabase.table("bookings").select("*").eq("id", booking_id).limit(1).execute()
        return (res.data or [None])[0]
    except Exception as e:  # noqa: BLE001
        log.warning("get booking %s failed: %s", booking_id, e)
        return None


def _booking_to_calendar_event(booking: dict) -> dict:
    metadata = booking.get("metadata") or {}
    kind = booking.get("kind") or "booking"
    return {
        "id": str(booking.get("id")),
        "title": booking.get("title") or "Confirmed booking",
        "type": kind,
        "booking_type": kind,
        "start_date": metadata.get("start_date"),
        "start_time": metadata.get("start_time"),
        "end_date": metadata.get("end_date"),
        "end_time": metadata.get("end_time"),
        "location": booking.get("location"),
        "notes": metadata.get("description") or "",
        "status": "Paid",
        "payment_status": "paid",
        "provider": metadata.get("provider"),
        "source": "booking",
    }


def _update_booking(booking_id, fields: dict) -> None:
    if not booking_id:
        return
    try:
        supabase.table("bookings").update(fields).eq("id", booking_id).execute()
    except Exception as e:  # noqa: BLE001
        log.warning("update booking %s failed: %s", booking_id, e)
