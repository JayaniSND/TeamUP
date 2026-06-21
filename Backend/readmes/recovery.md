![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

# BASELINE — Recovery Agent

**Agent name:** `recovery`
**Agent address:** `agent1q...` ← paste the address printed on boot

Detects fatigue / soreness / overtraining **and** broader behavioral patterns
across an athlete's history.

## What it does
Over the **Agent Chat Protocol**, reads the athlete's recent journal entries,
recovery logs, training, and metrics, and asks Claude for two reads:

- **Physical (~14 days):** overtraining/injury risk, including subtle
  *linguistic drift* (serve "explosive" → "muscling through") before pain is
  even mentioned — same body part sore 3+ sessions, load spikes, declining
  recovery score.
- **Behavioral arc (~30–60 days):** patterns that only show across timestamps —
  `confidence_rising`, `burnout_arc`, `momentum_dip`, `readiness_window`,
  `plateau`. On a positive arc it **chains to the next agent** (e.g. fires
  Logistics: "your best two weeks since January — there's a tournament in 18
  days, want me to register you?").

It writes insight cards the dashboard surfaces, and dedups repeat alerts within
72h (Agent Memory).

**When physical risk is medium or high it automatically chains to two agents:**
- **Fitness Agent** — to adjust the athlete's training plan and avoid loading the flagged area
- **Coaching Agent** — to advise strategy and technique adjustments that accommodate the injury

## How to use it
Send a note like:

> "Right knee sore again after intervals, third time this week."

or ask:

> "How's my body been?" / "Am I overtrained?"

It replies with a physical risk read (level, body parts, recommendation) and, when present, the behavioral pattern + the chained next steps. The Fitness and Coaching agents then run in the background and post their own insight cards to the dashboard.

## Built with
Fetch.ai uAgents · Agentverse · ASI:One · Anthropic Claude
