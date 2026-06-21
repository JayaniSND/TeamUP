"""logistics.py — Logistics specialist agent: flights, hotels, ITF
tournament search, a Stripe test-mode payment gate, and the athlete's
Google Calendar — all in one agent.

Receives logistics-related text — forwarded by the Librarian when an entry
is classified into the `logistics` section, or asked directly by a human
through ASI:One/Agentverse — extracts a travel intent with Claude, then:

  1. Queries the Flights agent and the Duffel Stays hotel agent (external,
     real Agentverse agents) for real options.
  2. Searches the ITF Women's World Tennis Tour calendar (via Browserbase/
     Stagehand) for W15/W25 tournaments.
  3. Creates an event on the athlete's Google Calendar for the trip dates.
  4. Replies with everything gathered. If tournaments were found, a
     follow-up reply with a number triggers a REAL Stripe test-mode
     payment (a small "booking assistance" fee) before continuing to the
     tournament's entry review screen — see PAYMENT DESIGN below.

PAYMENT DESIGN — read before changing this:
  This uses Stripe's TEST mode (sk_test_... key, test card numbers like
  4242 4242 4242 4242). It is a real Checkout Session and a real
  confirmed-paid check via Stripe's API — not a hardcoded "success"
  message. If you swap in a live secret key this becomes real money;
  don't do that without understanding what you're charging for.
  This fee is YOUR agent's own service fee, not a payment for an actual
  flight/hotel/tournament entry — the Flights/Hotels agents have their
  own separate payment system (FET/Skyfire) you don't control, and the
  ITF entry itself is still never auto-submitted (see SAFETY DESIGN
  below) — Stripe here only gates whether this agent continues to show
  you that entry review screen, nothing more.

SAFETY DESIGN — read before changing this file:
  This agent will, if IPIN_USERNAME/IPIN_PASSWORD are set, log in and fill
  the entry form for a chosen tournament. It deliberately does NOT contain
  any code path that clicks the final "submit / pay" action on the ITF
  site — not even after the Stripe fee above is paid. Paying this agent's
  service fee is not the same thing as authorizing a real federation
  entry; those stay two separate, separately-gated actions on purpose.

REAL-WORLD CONSTRAINT: ITF entry isn't a public "search and pay" flow.
It goes through the player's own IPIN account (https://ipin.itftennis.com/),
tied to their real ranking, with a fixed entry deadline — 18 days before
the Monday of the tournament week.

⚠️ ACTION NEEDED FROM YOU:
  - Stripe: dashboard.stripe.com → Developers → API keys → toggle "Test
    mode" → copy the Secret key (starts sk_test_). Set STRIPE_SECRET_KEY.
    `pip install stripe`. Without this key set, the payment gate is
    skipped entirely and the old direct-to-walkthrough behavior runs.
  - Google Calendar: see calendar_client.py's docstring for the one-time
    OAuth setup. Without it, the calendar step degrades gracefully.

⚠️ Per .env.example, LOGISTICS_ADDRESS is "owned by Dev 4." Coordinate
before this becomes the canonical logistics agent in your submission.

Run:  python -m agents.logistics   (from the Backend/ directory)
On boot it prints its address — paste that into .env as LOGISTICS_ADDRESS.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import date, datetime, timezone

import anthropic
import stripe
from pydantic import BaseModel
from stagehand import Stagehand
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    chat_protocol_spec,
)

from .common import calendar_client, config
from .common.booking_intent import booking_kinds_for_intent, classify_booking_intent
from .common.chat import decode_envelope, is_start, make_ack, make_chat, text_of

log = logging.getLogger("logistics")

# ── External Agentverse agents (not yours — plain chat only) ──────────
FLIGHTS_AGENT_ADDRESS = os.environ.get(
    "FLIGHTS_AGENT_ADDRESS",
    "agent1qd5pzya4xw2vuq8fcgqcympct4kwksrq2fled0l8ljygvpdpy6twjl607pw",
)
HOTELS_AGENT_ADDRESS = os.environ.get(
    "HOTELS_AGENT_ADDRESS",
    "agent1qgj8z70l5qstn0cq5lnn2q2mpjcpq4hu2rrm446lxrszchq0zv93ygq4sar",
)

# ── ITF tournament search (Browserbase / Stagehand) ────────────────────
CALENDAR_URL = "https://www.itftennis.com/en/tournament-calendar/womens-world-tennis-tour-calendar/"
TOUR_NAME = "Women's World Tennis Tour"
TIER = "W15/W25"

BROWSERBASE_API_KEY = os.environ.get("BROWSERBASE_API_KEY", "")
BROWSERBASE_PROJECT_ID = os.environ.get("BROWSERBASE_PROJECT_ID", "")
IPIN_USERNAME = os.environ.get("IPIN_USERNAME", "").strip()
IPIN_PASSWORD = os.environ.get("IPIN_PASSWORD", "").strip()

# ── Stripe (TEST MODE) ───────────────────────────────────────────────
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "").strip()
STRIPE_SUCCESS_URL = os.environ.get("STRIPE_SUCCESS_URL", "https://example.com/success")
STRIPE_CANCEL_URL = os.environ.get("STRIPE_CANCEL_URL", "https://example.com/cancel")
BOOKING_FEE_USD = float(os.environ.get("BOOKING_FEE_USD", "5.00"))
stripe.api_key = STRIPE_SECRET_KEY or None

REPLY_TIMEOUT_SECONDS = 30      # flights/hotels/tournament-search legs
PICK_TIMEOUT_SECONDS = 600      # waiting on a human to pick a tournament number
PAYMENT_TIMEOUT_SECONDS = 900   # waiting on Stripe checkout to complete

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

agent = Agent(
    name="logistics",
    seed=os.environ.get("LOGISTICS_SEED", "baseline-logistics-seed-v1"),
    port=int(os.environ.get("LOGISTICS_PORT", "8006")),
    mailbox=True,
)

chat_proto = Protocol(spec=chat_protocol_spec)
anthropic_client = anthropic.Anthropic(api_key=config.require_anthropic_key())


class TournamentListing(BaseModel):
    name: str
    location: str
    category: str = ""
    start_date: str = ""
    end_date: str = ""
    entry_deadline: str = ""
    entry_url: str = ""


class TournamentSearchResult(BaseModel):
    tournaments: list[TournamentListing]


# Single in-flight conversation, demo scale. Stages: "active" -> (tournaments
# found) "awaiting_pick" -> (number picked, Stripe configured) "awaiting_payment"
# -> entry walkthrough -> cleared.
current: dict | None = None


# ── Travel intent extraction (Claude) ──────────────────────────────────

def _extract_travel_intent(raw_text: str) -> dict | None:
    today = date.today().isoformat()
    prompt = (
        f"Today's date is {today}. An athlete wrote this note about travel "
        f"or an upcoming event:\n\n\"{raw_text}\"\n\n"
        "Extract a travel intent as JSON with exactly these keys: "
        '"destination" (city and/or region, or null if not mentioned), '
        '"start_date" (YYYY-MM-DD, resolving relative phrases like '
        '"in two weeks" against today\'s date, or null), '
        '"end_date" (YYYY-MM-DD — assume a 3-day trip if only one date is '
        'mentioned, or null), '
        '"travelers" (integer, default 1 if not mentioned). '
        "Output ONLY the JSON object, no commentary, no markdown fences."
    )
    response = anthropic_client.messages.create(
        model=config.CLASSIFY_MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        log.warning("Could not parse travel intent JSON: %s", text)
        return None
    if not data.get("destination"):
        return None
    data.setdefault("travelers", 1)
    return data


# ── Google Calendar ─────────────────────────────────────────────────────

def _maybe_create_calendar_event(intent: dict, raw_text: str) -> str | None:
    start_date = intent.get("start_date")
    end_date = intent.get("end_date")
    if not (start_date and end_date and _DATE_RE.match(start_date) and _DATE_RE.match(end_date)):
        log.info("Skipping calendar event — dates not resolved to YYYY-MM-DD: %s/%s", start_date, end_date)
        return None
    return calendar_client.create_event(
        summary=f"Trip: {intent['destination']}",
        start_date=start_date,
        end_date=end_date,
        location=intent["destination"],
        description=raw_text,
    )


# ── Stripe (TEST MODE) ───────────────────────────────────────────────────

def _create_checkout_session(tournament_name: str) -> tuple[str, str]:
    """Real Stripe test-mode Checkout Session. Returns (checkout_url, session_id)."""
    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": f"Booking assistance fee — {tournament_name}"},
                "unit_amount": int(round(BOOKING_FEE_USD * 100)),
            },
            "quantity": 1,
        }],
        success_url=STRIPE_SUCCESS_URL,
        cancel_url=STRIPE_CANCEL_URL,
    )
    return session.url, session.id


def _check_payment_status(session_id: str) -> bool:
    """Real check against Stripe's API — true only if actually paid."""
    session = stripe.checkout.Session.retrieve(session_id)
    return session.payment_status == "paid"


# ── ITF tournament search (Browserbase / Stagehand) ─────────────────────

def _stagehand_kwargs() -> dict:
    if not BROWSERBASE_API_KEY or not BROWSERBASE_PROJECT_ID:
        raise RuntimeError("BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID must be set in .env")
    return dict(
        env="BROWSERBASE",
        api_key=BROWSERBASE_API_KEY,
        project_id=BROWSERBASE_PROJECT_ID,
        model_name="claude-sonnet-4-6",
        model_client_options={"apiKey": config.require_anthropic_key()},
    )


async def _search_tournaments(location_hint: str | None) -> list[TournamentListing]:
    stagehand = Stagehand(**_stagehand_kwargs())
    await stagehand.init()
    log.info("Stagehand session: %s", stagehand.session_id)
    try:
        page = stagehand.page
        await page.goto(CALENDAR_URL)
        await page.act(f"filter the tournament list to only {TIER} category events")
        if location_hint:
            await page.act(f"if there is a location or country filter, set it to {location_hint}")
        result = await page.extract(
            instruction=(
                f"Extract every {TIER} tournament currently shown, including "
                "name, location, category, start date, end date, entry "
                "deadline if shown, and the URL to the tournament's own page "
                "if available."
            ),
            schema=TournamentSearchResult.model_json_schema(),
        )
        data = TournamentSearchResult.model_validate(result)
        return data.tournaments
    finally:
        await stagehand.close()


async def _prepare_entry(tournament: TournamentListing) -> str:
    """Walk toward entering a specific tournament. Never submits — see
    SAFETY DESIGN at the top of this file."""
    if not tournament.entry_url:
        return (
            f"I don't have a direct entry link for {tournament.name} from the "
            f"search results. You can find it on the ITF calendar directly: "
            f"{CALENDAR_URL}"
        )

    if not IPIN_USERNAME or not IPIN_PASSWORD:
        return (
            f"To actually enter {tournament.name}, log into your own IPIN "
            f"account and submit the entry yourself — entries are tied to a "
            f"real ranking and a real account, so this isn't something I can "
            f"do generically. I don't have IPIN credentials configured.\n"
            f"Direct link: {tournament.entry_url}\n"
            f"Entry deadline: {tournament.entry_deadline or '18 days before the Monday of tournament week'}"
        )

    stagehand = Stagehand(**_stagehand_kwargs())
    await stagehand.init()
    log.info("Stagehand entry-prep session: %s", stagehand.session_id)
    try:
        page = stagehand.page
        await page.goto(tournament.entry_url)
        await page.act("click the Enter button for this tournament")
        login_present = await page.observe("find the IPIN username and password login fields")
        if login_present:
            await page.act(f"enter the username {IPIN_USERNAME} in the IPIN login username field")
            await page.act(f"enter the password {IPIN_PASSWORD} in the IPIN login password field")
            await page.act("submit the login form")
        await page.act("proceed to the entry confirmation and payment review screen, but do not submit or pay")
        summary = await page.extract(
            instruction=(
                "Describe exactly what this entry/payment review screen shows: "
                "the tournament, the entry fee or charge amount, the deadline, "
                "and any draw (singles/doubles) being entered. Do not click "
                "anything further."
            ),
            schema={"type": "object", "properties": {"summary": {"type": "string"}}},
        )
        review_text = summary.get("summary", "(could not read the review screen)")
        return (
            f"I've gotten as far as the entry review screen for {tournament.name} "
            f"— here's exactly what it shows:\n\n{review_text}\n\n"
            f"I'm stopping here on purpose. This is a real entry tied to a real "
            f"account and real money — review this yourself in the actual "
            f"browser and submit it only if it's correct.\n"
            f"Session replay: https://browserbase.com/sessions/{stagehand.session_id}"
        )
    finally:
        await stagehand.close()


async def _run_tournament_leg(ctx: Context, req: dict, location_hint: str | None):
    try:
        req["tournaments"] = await _search_tournaments(location_hint)
    except Exception as e:  # noqa: BLE001
        log.warning("Tournament search failed: %s", e)
        req["tournaments"] = []
        req["tournament_error"] = str(e)
    req["legs_pending"].discard("tournament")
    await _maybe_finish(ctx)


# ── Orchestration ────────────────────────────────────────────────────────

def _legs_for_booking_intent(booking_intent: str) -> set[str]:
    if booking_intent == "fee_only":
        return set()
    kinds = set(booking_kinds_for_intent(booking_intent))
    legs: set[str] = set()
    if "flight" in kinds:
        legs.add("flights")
    if "hotel" in kinds:
        legs.add("hotels")
    if booking_intent == "general":
        legs.add("tournament")
    return legs


def _compose_fee_summary() -> str:
    fee_cents = int(round(BOOKING_FEE_USD * 100))
    return "\n".join([
        "Fee Summary",
        "* Base price: $0.00",
        f"* Service fee: ${fee_cents / 100:.2f}",
        f"* Total: ${fee_cents / 100:.2f}",
    ])


async def _kick_off_request(
    ctx: Context,
    sender: str,
    user_id: str,
    raw_text: str,
    booking_intent_hint: str | None = None,
):
    global current

    if current is not None:
        await ctx.send(
            sender,
            make_chat(
                "I'm still pulling options for a previous request — give me "
                "a moment and try again shortly.",
                end_session=True,
            ),
        )
        return

    booking_intent = classify_booking_intent(raw_text, booking_intent_hint)
    if booking_intent == "fee_only":
        await ctx.send(sender, make_chat(_compose_fee_summary(), end_session=True))
        return

    intent = await asyncio.to_thread(_extract_travel_intent, raw_text)
    if not intent:
        await ctx.send(
            sender,
            make_chat(
                "I see a logistics note but couldn't tell where you're "
                "headed. Mind telling me the destination and rough dates?",
                end_session=True,
            ),
        )
        return

    destination = intent["destination"]
    start_date = intent.get("start_date") or "a date to be confirmed"
    end_date = intent.get("end_date") or "a date to be confirmed"
    travelers = intent.get("travelers", 1)

    calendar_link = (
        await asyncio.to_thread(_maybe_create_calendar_event, intent, raw_text)
        if booking_intent == "general"
        else None
    )
    legs_pending = _legs_for_booking_intent(booking_intent)

    current = {
        "stage": "active",
        "reply_to": sender,
        "user_id": user_id,
        "booking_intent": booking_intent,
        "destination": destination,
        "start_date": start_date,
        "end_date": end_date,
        "travelers": travelers,
        "calendar_link": calendar_link,
        "flights_reply": None,
        "hotels_reply": None,
        "tournaments": None,
        "tournament_error": None,
        "legs_pending": legs_pending,
        "started_at": datetime.now(timezone.utc),
    }

    flights_query = f"Find flights to {destination} from {start_date} to {end_date} for {travelers} adult(s)."
    hotels_query = f"Find hotels in {destination} from {start_date} to {end_date} for {travelers} guest(s)."

    if "flights" in legs_pending:
        ctx.logger.info("Querying flights agent for %s: %s", user_id, flights_query)
        await ctx.send(FLIGHTS_AGENT_ADDRESS, make_chat(flights_query))

    if "hotels" in legs_pending:
        ctx.logger.info("Querying hotels agent for %s: %s", user_id, hotels_query)
        await ctx.send(HOTELS_AGENT_ADDRESS, make_chat(hotels_query))

    if "tournament" in legs_pending:
        ctx.logger.info("Starting tournament search for %s near %s", user_id, destination)
        asyncio.create_task(_run_tournament_leg(ctx, current, destination))


def _compose_summary(req: dict) -> str:
    booking_intent = req.get("booking_intent") or "general"
    if booking_intent == "flight_only":
        return "\n".join([
            "Flight Options",
            "Option 1",
            f"* Date/time: {req['start_date']} to {req['end_date']}",
            f"* Route: To {req['destination']}",
            "* Airline: See flight search result",
            "* Price: See flight search result",
            f"* Why it works: {req['flights_reply'] or 'No response from the flights agent yet.'}",
            "",
            "Next Step",
            "Choose a flight to continue to payment.",
        ])

    if booking_intent == "hotel_only":
        return "\n".join([
            "Hotel Options",
            "Option 1",
            f"* Check-in: {req['start_date']}",
            f"* Check-out: {req['end_date']}",
            f"* Location: {req['destination']}",
            "* Price: See hotel search result",
            f"* Why it works: {req['hotels_reply'] or 'No response from the hotels agent yet.'}",
            "",
            "Next Step",
            "Choose a hotel to continue to payment.",
        ])

    if booking_intent == "flight_hotel":
        return "\n\n".join([
            "\n".join([
                "Flight Options",
                "Option 1",
                f"* Date/time: {req['start_date']} to {req['end_date']}",
                f"* Route: To {req['destination']}",
                "* Airline: See flight search result",
                "* Price: See flight search result",
                f"* Why it works: {req['flights_reply'] or 'No response from the flights agent yet.'}",
            ]),
            "\n".join([
                "Hotel Options",
                "Option 1",
                f"* Check-in: {req['start_date']}",
                f"* Check-out: {req['end_date']}",
                f"* Location: {req['destination']}",
                "* Price: See hotel search result",
                f"* Why it works: {req['hotels_reply'] or 'No response from the hotels agent yet.'}",
            ]),
            "\n".join(["Next Step", "Choose a flight or hotel to continue to payment."]),
        ])

    lines = [f"🧳 Logistics for {req['destination']} ({req['start_date']} → {req['end_date']}):"]
    lines.append("\n✈️ Flights:")
    lines.append(req["flights_reply"] or "  (no response from the flights agent yet)")
    lines.append("\n🏨 Hotels:")
    lines.append(req["hotels_reply"] or "  (no response from the hotels agent yet)")
    lines.append(f"\n🎾 {TIER} tournaments ({TOUR_NAME}):")
    tournaments = req.get("tournaments") or []
    if tournaments:
        for i, t in enumerate(tournaments, start=1):
            lines.append(
                f"  {i}. {t.name} — {t.location}" + (f" ({t.category})" if t.category else "") + "\n"
                f"     {t.start_date} → {t.end_date}"
                + (f" | entry deadline: {t.entry_deadline}" if t.entry_deadline else "")
            )
        lines.append("  Reply with a number to see what entering that one would involve.")
    elif req.get("tournament_error"):
        lines.append(f"  (tournament search failed: {req['tournament_error']})")
    else:
        lines.append("  No matching tournaments found right now.")
    lines.append("\n📅 Calendar:")
    if req["calendar_link"]:
        lines.append(f"  Added to your calendar: {req['calendar_link']}")
    else:
        lines.append("  Couldn't add this to your calendar (dates unclear, or calendar isn't authorized yet).")
    lines.append(
        "\nThese are options only — nothing has been booked, entered, or "
        "paid for. Tell me what you'd like and we can take the next step."
    )
    return "\n".join(lines)


async def _finish_active_stage(ctx: Context, req: dict):
    global current
    has_tournaments = req.get("booking_intent") == "general" and bool(req.get("tournaments"))
    await ctx.send(req["reply_to"], make_chat(_compose_summary(req), end_session=not has_tournaments))
    if has_tournaments:
        req["stage"] = "awaiting_pick"
        req["started_at"] = datetime.now(timezone.utc)
        current = req
    else:
        current = None


async def _maybe_finish(ctx: Context):
    req = current
    if not req or req["stage"] != "active" or req["legs_pending"]:
        return
    await _finish_active_stage(ctx, req)


async def _start_payment_or_skip(ctx: Context, sender: str, chosen: TournamentListing):
    """If Stripe is configured, charge the demo service fee and wait for
    real confirmation before continuing. If not configured, fall back to
    the old behavior — go straight to the entry walkthrough."""
    global current

    if not STRIPE_SECRET_KEY:
        summary = await _prepare_entry(chosen)
        await ctx.send(sender, make_chat(summary, end_session=True))
        current = None
        return

    try:
        checkout_url, session_id = await asyncio.to_thread(_create_checkout_session, chosen.name)
    except Exception as e:  # noqa: BLE001 — don't crash the agent on a Stripe error
        log.warning("Stripe checkout creation failed: %s", e)
        await ctx.send(
            sender,
            make_chat(f"Couldn't start the payment step ({e}) — try again shortly.", end_session=True),
        )
        current = None
        return

    current["stage"] = "awaiting_payment"
    current["chosen_tournament"] = chosen
    current["stripe_session_id"] = session_id
    current["started_at"] = datetime.now(timezone.utc)

    await ctx.send(
        sender,
        make_chat(
            f"To pull up entry details for {chosen.name}, there's a "
            f"${BOOKING_FEE_USD:.2f} booking assistance fee (Stripe TEST mode "
            f"— use card 4242 4242 4242 4242, any future date/CVC, no real "
            f"charge). Pay here: {checkout_url}\n"
            f"I'll continue automatically once payment is confirmed."
        ),
    )


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    global current
    await ctx.send(sender, make_ack(msg))

    if current is not None and current["stage"] == "active" and sender in (FLIGHTS_AGENT_ADDRESS, HOTELS_AGENT_ADDRESS):
        body = text_of(msg)
        if sender == FLIGHTS_AGENT_ADDRESS:
            current["flights_reply"] = body
            current["legs_pending"].discard("flights")
        else:
            current["hotels_reply"] = body
            current["legs_pending"].discard("hotels")
        await _maybe_finish(ctx)
        return

    if is_start(msg):
        await ctx.send(
            sender,
            make_chat(
                "👋 Logistics agent ready. Tell me about an upcoming "
                "tournament or trip and I'll pull flight, hotel, and "
                "tournament options, and add it to your calendar."
            ),
        )
        return

    raw = text_of(msg)
    if not raw.strip():
        return

    if current is not None and current["stage"] == "awaiting_pick" and sender == current["reply_to"]:
        choice = raw.strip()
        if choice.isdigit():
            idx = int(choice) - 1
            tournaments = current["tournaments"]
            if 0 <= idx < len(tournaments):
                chosen = tournaments[idx]
                ctx.logger.info("Tournament picked: %s", chosen.name)
                await _start_payment_or_skip(ctx, sender, chosen)
                return
        current = None

    if current is not None:
        await ctx.send(
            sender,
            make_chat("I'm still working on a previous request — give me a moment.", end_session=True),
        )
        return

    env = decode_envelope(raw, config.DEFAULT_USER_ID)
    await _kick_off_request(
        ctx,
        sender,
        env["user_id"],
        env["text"],
        env.get("bookingIntent") or env.get("booking_intent"),
    )


@chat_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.debug("ack from %s for %s", sender, msg.acknowledged_msg_id)


@agent.on_interval(period=10.0)
async def flush_stale(ctx: Context):
    global current
    if current is None:
        return
    age = (datetime.now(timezone.utc) - current["started_at"]).total_seconds()

    if current["stage"] == "active" and age > REPLY_TIMEOUT_SECONDS:
        await _finish_active_stage(ctx, current)

    elif current["stage"] == "awaiting_pick" and age > PICK_TIMEOUT_SECONDS:
        ctx.logger.info("Clearing stale tournament pick window (no reply for %.0fs)", age)
        current = None

    elif current["stage"] == "awaiting_payment":
        req = current
        paid = await asyncio.to_thread(_check_payment_status, req["stripe_session_id"])
        if paid:
            ctx.logger.info("Stripe payment confirmed for session %s", req["stripe_session_id"])
            chosen = req["chosen_tournament"]
            reply_to = req["reply_to"]
            current = None
            await ctx.send(reply_to, make_chat("✅ Payment confirmed — pulling up entry details now..."))
            summary = await _prepare_entry(chosen)
            await ctx.send(reply_to, make_chat(summary, end_session=True))
        elif age > PAYMENT_TIMEOUT_SECONDS:
            ctx.logger.info("Payment window expired for session %s", req["stripe_session_id"])
            await ctx.send(
                req["reply_to"],
                make_chat("Payment window expired — ask me again if you'd still like to proceed.", end_session=True),
            )
            current = None


agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    print(f"[logistics] address: {agent.address}")
    agent.run()
