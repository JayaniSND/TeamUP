![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

# BASELINE — Librarian Agent

**Agent name:** `librarian`
**Agent address:** `agent1q...` ← paste the address printed on boot

Classifies an athlete's raw journal dump and files it into the right sections.

## What it does
Over the **Agent Chat Protocol**, takes a raw dump (voice transcript / text /
transcribed notebook page) and uses Claude to split it into discrete entries,
each filed under one section:
`training · performance · match_results · recovery · coaching · logistics ·
sponsorship · goals · media_notes`.

Each entry is written to the dashboard backend. When used on its own it also
autonomously notifies the relevant specialist agents (Recovery, Performance,
Sponsorship, Logistics).

## How to use it
Send notes like:

> "Backhand felt flat in practice, knee a little sore, need to eat more before
> sessions."

It replies with the sectioned breakdown.

## Built with
Fetch.ai uAgents · Agentverse · ASI:One · Anthropic Claude
