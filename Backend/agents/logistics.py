"""logistics.py — Logistics specialist agent: flights, hotels, ITF
tournament search, and the athlete's Google Calendar — all in one agent.

Receives logistics-related text — forwarded by the Librarian when an entry
is classified into the `logistics` section, or asked directly by a human
through ASI:One/Agentverse — extracts a travel intent with Claude, then:

  1. Queries the Flights agent and the Duffel Stays hotel agent (external,
     real Agentverse agents) for real options.
  2. Searches the ITF Women's World Tennis Tour calendar (via Browserbase/
     Stagehand) for W15/W25 tournaments — the entry-level pro circuit that
     fits an elite junior transitioning into low-level pro events.
  3. Creates an event on the athlete's Google Calendar for the trip dates.
  4. Replies with everything gathered. If tournaments were found, a
     follow-up reply with a number walks toward that tournament's entry
     page — see SAFETY DESIGN below for where that deliberately stops.

REAL-WORLD CONSTRAINT: ITF entry isn't a public "search and pay" flow.
It goes through the player's own IPIN account (https://ipin.itftennis.com/),
tied to their real ranking, with a fixed entry deadline — 18 days before
the Monday of the tournament week. IPIN is a per-player account, not a
family/guardian account, so this agent talks about "your IPIN account,"
not a guardian's — but note: if the player entering is a minor, ITF's own
Age Eligibility Rules (AER) and any account safeguarding requirements
still apply regardless of what this agent does or doesn't say; nothing
here changes or bypasses those.

SAFETY DESIGN — read before changing this file:
  This agent will, if IPIN_USERNAME/IPIN_PASSWORD are set, log in and fill
  the entry form for a chosen tournament. It deliberately does NOT contain
  any code path that clicks the final "submit / pay" action — not even
  behind a chat "CONFIRM" reply. A chat message is too low a bar to gate a
  real, irreversible, real-money transaction behind, especially on a flow
  that's never been run against the live site. The last step — reviewing
  the filled form and the actual charge, then submitting — is left to the
  actual account holder, in the real browser, on purpose.

⚠️ ACTION NEEDED FROM YOU for the calendar piece — see calendar_client.py's
docstring for the full one-time Google OAuth setup. Without it, the
calendar step just degrades gracefully (skipped, noted in the reply).

⚠️ Per .env.example, LOGISTICS_ADDRESS is "owned by Dev 4." Coordinate
before this becomes the canonical logistics agent in your submission.

Run:  python -m agents.logistics   (from the Backend/ directory)
On boot it prints its address — paste that into .env as LOGISTICS_ADDRESS.

Required env vars: ANTHROPIC_API_KEY, BROWSERBASE_API_KEY,
BROWSERBASE_PROJECT_ID. Optional: IPIN_USERNAME/IPIN_PASSWORD,
FLIGHTS_AGENT_ADDRESS/HOTELS_AGENT_ADDRESS overrides.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import date, datetime, timezone

import anthropic
from pydantic import BaseModel
from stagehand import Stagehand
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    chat_protocol_spec,
)

from .common import calendar_client, config
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
TIER = "W15/W25"  # entry-level pro circuit — the realistic level for an elite junior turning pro

BROWSERBASE_API_KEY = os.environ.get("BROWSERBASE_API_KEY", "")
BROWSERBASE_PROJECT_ID = os.environ.get("BROWSERBASE_PROJECT_ID", "")
IPIN_USERNAME = os.environ.get("IPIN_USERNAME", "").strip()
IPIN_PASSWORD = os.environ.get("IPIN_PASSWORD", "").strip()

REPLY_TIMEOUT_SECONDS = 30  # for the flights/hotels/tournament-search legs
PICK_TIMEOUT_SECONDS = 600  # for waiting on a human to pick a tournament number

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
    category: str = ""  # e.g. "W15", "W25"
    start_date: str = ""
    end_date: str = ""
    entry_deadline: str = ""
    entry_url: str = ""


class TournamentSearchResult(BaseModel):
    tournaments: list[TournamentListing]


# Single in-flight conversation, demo scale. Stages: "active" (waiting on
# flights/hotels/tournament legs) -> "awaiting_pick" (tournaments found,
# waiting for a number) -> cleared.
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
    """Open a fresh Browserbase session, navigate the ITF calendar, and
    extract W15/W25 tournaments. Closes the session before returning."""
    stagehand = Stagehand(**_stagehand_kwargs())
    await stagehand.init()
    log.info("Stagehand session: %s", stagehand.session_id)
    try:
        page = stagehand.page
        await page.goto(CALENDAR_URL)

        # TODO: verify this instruction actually surfaces a level filter on
        # the live site — refine wording after watching the session replay.
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
    """Walk toward entering a specific tournament. Logs in only if IPIN
    credentials are configured. Stops at the final review/payment screen —
    see SAFETY DESIGN at the top of this file. Never submits anything."""
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

        # TODO: untested against the live IPIN login/entry screen.
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
    """Runs as a background task so it doesn't block flights/hotels from
    proceeding in parallel. Mutates req in place (same dict object the
    global `current` points to) and checks for completion when done."""
    try:
        req["tournaments"] = await _search_tournaments(location_hint)
    except Exception as e:  # noqa: BLE001 — degrade this leg, don't crash the agent
        log.warning("Tournament search failed: %s", e)
        req["tournaments"] = []
        req["tournament_error"] = str(e)
    req["legs_pending"].discard("tournament")
    await _maybe_finish(ctx)


# ── Orchestration ────────────────────────────────────────────────────────

async def _kick_off_request(ctx: Context, sender: str, user_id: str, raw_text: str):
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

    calendar_link = await asyncio.to_thread(_maybe_create_calendar_event, intent, raw_text)

    current = {
        "stage": "active",
        "reply_to": sender,
        "user_id": user_id,
        "destination": destination,
        "start_date": start_date,
        "end_date": end_date,
        "travelers": travelers,
        "calendar_link": calendar_link,
        "flights_reply": None,
        "hotels_reply": None,
        "tournaments": None,
        "tournament_error": None,
        "legs_pending": {"flights", "hotels", "tournament"},
        "started_at": datetime.now(timezone.utc),
    }

    flights_query = f"Find flights to {destination} from {start_date} to {end_date} for {travelers} adult(s)."
    hotels_query = f"Find hotels in {destination} from {start_date} to {end_date} for {travelers} guest(s)."

    ctx.logger.info("Querying flights agent for %s: %s", user_id, flights_query)
    await ctx.send(FLIGHTS_AGENT_ADDRESS, make_chat(flights_query))

    ctx.logger.info("Querying hotels agent for %s: %s", user_id, hotels_query)
    await ctx.send(HOTELS_AGENT_ADDRESS, make_chat(hotels_query))

    ctx.logger.info("Starting tournament search for %s near %s", user_id, destination)
    asyncio.create_task(_run_tournament_leg(ctx, current, destination))


def _compose_summary(req: dict) -> str:
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
    """Send the combined summary. If tournaments were found, stay open for
    a follow-up pick; otherwise close out the conversation."""
    global current
    has_tournaments = bool(req.get("tournaments"))
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


@chat_proto.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    global current
    await ctx.send(sender, make_ack(msg))

    # Replies from the external Flights/Hotels agents.
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

    # Follow-up: picking a tournament number after a completed search.
    if current is not None and current["stage"] == "awaiting_pick" and sender == current["reply_to"]:
        choice = raw.strip()
        if choice.isdigit():
            idx = int(choice) - 1
            tournaments = current["tournaments"]
            if 0 <= idx < len(tournaments):
                chosen = tournaments[idx]
                ctx.logger.info("Preparing entry info for %s", chosen.name)
                summary = await _prepare_entry(chosen)
                await ctx.send(sender, make_chat(summary, end_session=True))
                current = None
                return
        # Not a valid pick — don't get the conversation stuck, fall through
        # and treat this as a fresh request instead.
        current = None

    if current is not None:
        await ctx.send(
            sender,
            make_chat("I'm still working on a previous request — give me a moment.", end_session=True),
        )
        return

    env = decode_envelope(raw, config.DEFAULT_USER_ID)
    await _kick_off_request(ctx, sender, env["user_id"], env["text"])


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


agent.include(chat_proto, publish_manifest=True)

if __name__ == "__main__":
    print(f"[logistics] address: {agent.address}")
    agent.run()