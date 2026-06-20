![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

# BASELINE — Orchestrator Agent

**Agent name:** `orchestrator`
**Agent address:** `agent1q...` ← paste the address printed on boot

A self-organizing performance journal for self-managed individual-sport
athletes (tennis first). Brain-dump after practice or a match and this agent
files every piece into the right section, watches for overtraining, and lines
up your next tournament — no custom frontend required.

## What it does
Receives a raw dump over the **Agent Chat Protocol** and performs multi-step
orchestration:
1. Delegates classification + filing to the **Librarian** agent.
2. From the classified sections, triggers the relevant specialists —
   **Recovery**, **Performance**, **Sponsorship**, and **Logistics**.
3. Correlates their replies and returns one consolidated answer in the same
   ASI:One session.

Claude does the reasoning (classification + recovery / performance /
sponsorship synthesis).

## How to use it
Send a natural-language message such as:

> "Worked on my serve today, felt sharp. Right knee was sore again after the
> long session. Got a tournament in San Jose in two weeks."

It replies with the filed sections, any overtraining flag, and the logistics
hand-off.

## Built with
Fetch.ai uAgents · Agentverse · ASI:One · Anthropic Claude
