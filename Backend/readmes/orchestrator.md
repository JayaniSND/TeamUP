![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)

# BASELINE — Orchestrator Agent

**Agent name:** `orchestrator`
**Agent address:** `agent1q...` ← paste the address printed on boot

A self-organizing performance journal for self-managed individual-sport
athletes (tennis first). Brain-dump after practice or a match and this agent
files every piece into the right section, watches for overtraining, and lines
up your next tournament — no custom frontend required.

## What it does
The single ASI:One gateway. On each message it reads the athlete's **intent**
with Claude and routes (framework v4 §6a):

- **Log** ("just finished practice, serve felt off, knee sore") → delegates to
  the **Librarian** to classify + file, then triggers the relevant specialists
  (**Recovery**, **Performance**, **Sponsorship**, **Logistics**), correlates
  their replies, and returns one consolidated answer.
- **Ask** ("how's my serve trending?", "what patterns do you see in my losses?")
  → RAG over the journal via `/chat`, returns a grounded answer with sources.
- **Action** ("am I overtrained?", "find me a tournament") → routes straight to
  the specialist that owns it and relays the result.

All over the **Agent Chat Protocol**, in one chat session. Claude does the
reasoning (intent routing + classification + specialist synthesis).

## How to use it
Send a natural-language message such as:

> "Worked on my serve today, felt sharp. Right knee was sore again after the
> long session. Got a tournament in San Jose in two weeks."

It replies with the filed sections, any overtraining flag, and the logistics
hand-off.

## Built with
Fetch.ai uAgents · Agentverse · ASI:One · Anthropic Claude
