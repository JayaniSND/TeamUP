![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

# BASELINE — Logistics Agent

**Agent name:** `logistics`
**Agent address:** `agent1q...` ← paste the address printed on boot

Handles the full travel + tournament pipeline: flights, hotels, ITF tournament search, Google Calendar, and an optional Stripe-gated entry walkthrough — all in one interactive agent.

## What it does

On a travel or tournament note (forwarded by the Librarian or sent directly), it:

1. Extracts destination, dates, and traveler count from the message using Claude
2. Queries two **external Agentverse agents** in parallel — a Flights agent and a Duffel Stays hotel agent — for real options
3. Scrapes the ITF Women's World Tennis Tour calendar (W15/W25) via **Browserbase/Stagehand** for matching tournaments
4. Creates an event on the athlete's **Google Calendar** for the trip dates
5. Replies with a combined summary of flights, hotels, and tournament listings

If tournaments were found, the conversation enters an interactive stage:
- The athlete replies with a **number** to select a tournament
- If `STRIPE_SECRET_KEY` is set, a **real Stripe TEST-mode payment** ($5.00 booking assistance fee) is charged before continuing — the agent polls for payment confirmation on a 10-second interval
- After payment (or if Stripe isn't configured), it uses Browserbase to navigate toward the tournament's entry review screen via IPIN, shows exactly what the screen says, and **stops** — it does not submit or pay the real entry

## State machine

```
active  →  awaiting_pick  →  awaiting_payment  →  [entry walkthrough]  →  cleared
```

- **active:** waiting for Flights + Hotels agents + tournament scrape to complete (30s timeout, then flushes whatever arrived)
- **awaiting_pick:** waiting for athlete to pick a tournament number (10-minute timeout)
- **awaiting_payment:** polling Stripe every 10s until paid or 15-minute timeout

## Safety design

This agent deliberately has no code path that clicks the final "submit/pay" action on the ITF site — even after the Stripe fee is paid. The Stripe fee only gates whether the agent continues to the review screen; it does not authorize or perform a real tournament entry.

## Setup

Required env vars (in `Backend/.env`):

| Var | Purpose |
|---|---|
| `BROWSERBASE_API_KEY` | Browserbase API key |
| `BROWSERBASE_PROJECT_ID` | Browserbase project ID |
| `STRIPE_SECRET_KEY` | Stripe TEST-mode secret key (`sk_test_...`) — omit to skip payment gate |
| `STRIPE_SUCCESS_URL` | Redirect URL on successful Stripe payment |
| `STRIPE_CANCEL_URL` | Redirect URL on cancelled Stripe payment |
| `IPIN_USERNAME` / `IPIN_PASSWORD` | ITF IPIN credentials for entry walkthrough — omit to show a manual link instead |
| `LOGISTICS_ADDRESS` | This agent's own address (paste from boot output) |
| `FLIGHTS_AGENT_ADDRESS` | External Agentverse Flights agent address |
| `HOTELS_AGENT_ADDRESS` | External Agentverse Hotels agent address |

Google Calendar requires a one-time OAuth setup — see `common/calendar_client.py`.

## How to use it

Send a note like:

> "There's a W15 tournament in San Jose in two weeks I want to enter — can you find flights and hotels too?"

It replies with all three legs combined. Reply with a number to go deeper on a specific tournament.

## Run

```
python -m agents.logistics   # from Backend/
```

Prints its address on boot — paste into `.env` as `LOGISTICS_ADDRESS`.

## Built with
Fetch.ai uAgents · Agentverse · ASI:One · Browserbase/Stagehand · Google Calendar · Stripe (TEST mode) · Anthropic Claude · ITF Women's World Tennis Tour
