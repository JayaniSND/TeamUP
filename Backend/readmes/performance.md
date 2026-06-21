![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

# BASELINE — Performance Agent

**Agent name:** `performance`
**Agent address:** `agent1q...` ← paste the address printed on boot

Summarizes an athlete's win/loss and skill trends.

## What it does
Over the **Agent Chat Protocol**, reads recent match results, training sessions,
and metrics from the journal backend and uses Claude to produce a grounded
performance summary: overall trend, strongest and weakest area, and one concrete
improvement focus. Writes a visible insight to the dashboard.

**When a consistent weak area is detected** (and trend is steady or declining), it automatically chains to the **Coaching Agent** with that weakness as context, so the athlete receives targeted technique advice alongside the performance summary.

## How to use it
Send a note like:

> "Won my match 6-3, 6-4 but my second serve let me down again."

It replies with your form trend and a focus recommendation. If a persistent weakness is identified, the Coaching Agent will follow up with technique advice — and Coaching may in turn brief the Fitness Agent on the conditioning work needed.

## Built with
Fetch.ai uAgents · Agentverse · ASI:One · Anthropic Claude
