![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

# BASELINE — Fitness Agent

**Agent name:** `fitness`
**Agent address:** `agent1q...` ← paste the address printed on boot

Builds a personalised weekly training schedule through conversation, then writes it to the athlete's calendar.

## What it does

The Fitness agent runs in two modes:

**Interactive (direct chat):** guides the athlete through a short conversation to build their schedule for the week.

1. Asks three quick questions in one message: which days are free, how long per session, and what the weekly focus is (recovery / performance / pre-competition / maintenance).
2. Reads the athlete's training history, recovery logs, and any injury context, then uses Claude to generate a concrete 7-day plan — rest days included, intensity adjusted for load and soreness.
3. Presents the plan and asks for confirmation.
4. On confirmation, writes each session to the athlete's calendar so it shows up in the Schedule panel of the dashboard.
5. If the athlete requests changes, re-generates the plan and re-asks.

**Background (chained from Recovery or Coaching):** when the Recovery agent detects a medium/high injury risk, or the Coaching agent identifies a physical conditioning gap, they automatically chain to Fitness. In background mode the agent generates a draft plan and writes it to the dashboard as an insight card — no calendar write yet. The athlete can then open a direct chat to confirm.

## Chains it receives

| Source | Trigger |
|---|---|
| Recovery Agent | medium / high injury risk detected |
| Coaching Agent | physical/conditioning gap in technique advice |

## How to use it

Start with:

> "Build me a training plan for next week."

or

> "My knee has been sore — adjust my schedule."

It will ask follow-up questions, propose a schedule, and add confirmed sessions to your calendar.

## Built with
Fetch.ai uAgents · Agentverse · ASI:One · Anthropic Claude
