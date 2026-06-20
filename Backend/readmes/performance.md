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

## How to use it
Send a note like:

> "Won my match 6-3, 6-4 but my second serve let me down again."

It replies with your form trend and a focus recommendation.

## Built with
Fetch.ai uAgents · Agentverse · ASI:One · Anthropic Claude
