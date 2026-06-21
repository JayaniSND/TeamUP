![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

# BASELINE — Scout Agent

**Agent name:** `scout`
**Agent address:** `agent1q...` ← paste the address printed on boot

Researches an opponent and hands the athlete a tactical edge.

## What it does
Over the **Agent Chat Protocol**, on a logged match (or an opponent query) it
scrapes the opponent's recent results via **Browserbase** (with a cached
fallback), uses Claude to summarize their patterns, strengths, and weaknesses,
and writes a `coaching` entry + dashboard insight with one concrete tactical
recommendation, then replies.

## How to use it
Send a note like:

> "Played Tanaka today and lost — what should I do differently next time?"

It replies with the opponent's patterns and a tactical plan to target their
weaknesses. It also writes a `coaching` entry to the database and **chains to
the Coaching agent**, which will send a follow-up message with a concrete
game-plan tailored to those weaknesses.

## Built with
Fetch.ai uAgents · Agentverse · ASI:One · Browserbase · Anthropic Claude
