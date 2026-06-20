# BASELINE — Agent Layer (Dev 3)

The Fetch.ai-facing half of BASELINE: real **uAgents** that talk over the
standardized **Agent Chat Protocol**, registered on **Agentverse**, reachable
through **ASI:One**, with **Claude** doing the reasoning inside them.

> Track: UC Berkeley AI Hackathon 2026 — Fetch.ai. This folder is the Dev 3
> deliverable (Orchestrator + Librarian + Recovery agents).

## What's here

```
Backend/
├── agents/
│   ├── orchestrator.py     # ASI:One entry point — conducts the whole loop
│   ├── librarian.py        # classify a dump → file into sections
│   ├── recovery.py         # detect overtraining / injury-risk patterns
│   └── common/
│       ├── config.py       # SECTIONS, models, addresses, env loading
│       ├── chat.py         # chat-protocol helpers (+ session content)
│       ├── claude.py       # Claude classify + overtraining (structured outputs)
│       └── backend_client.py  # async client for Dev 2's FastAPI
├── readmes/                # Agentverse "Overview" READMEs (one per agent)
├── mock_backend.py         # local stand-in for Dev 2 (seeded history)
├── run_local.py            # one-command OFFLINE end-to-end test (Bureau)
├── send_dump.py            # message a deployed/mailbox agent and print replies
├── asi_ping.py             # optional ASI:One probe for the bonus clip
├── requirements.txt
└── .env.example
```

## Architecture

```
            (ASI:One / Agentverse "Chat with Agent")
                          │  chat protocol
                          ▼
                 ┌──────────────────┐
                 │   Orchestrator   │  multi-step planning + routing
                 └───┬───────────┬──┘
            chat ▼              ▼ chat
         ┌───────────┐   ┌───────────┐        ┌──────────────┐
         │ Librarian │   │ Recovery  │        │  Logistics   │
         │ (Claude)  │   │ (Claude)  │        │  (Dev 4)     │
         └─────┬─────┘   └─────┬─────┘        └──────────────┘
               └──────┬────────┘
                      ▼  REST
            Dev 2 FastAPI (entries, metrics, flags)
```

The Orchestrator is the single agent a user talks to. It delegates
classification to the Librarian, routes injury notes to Recovery and
tournament notes to Logistics, then composes one answer. Each worker is **also
independently usable** through ASI:One on its own.

## Setup

```bash
cd Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then fill in ANTHROPIC_API_KEY
```

## Run it locally (offline, one command)

The fastest way to see the full loop:

```bash
# terminal 1 — the data backend stand-in
uvicorn mock_backend:app

# terminal 2 — all agents + a test user, in one process
python run_local.py
```

You'll see the demo dump classified into sections, an overtraining flag on the
seeded knee history, and the logistics hand-off — all printed as chat replies.

## Run it as real Agentverse agents (submission path)

Each agent runs as its own process with a mailbox, so Agentverse/ASI:One can
reach it.

```bash
# one terminal each
python -m agents.recovery        # prints RECOVERY address
python -m agents.librarian       # prints LIBRARIAN address
python -m agents.orchestrator    # prints ORCHESTRATOR address
```

1. On first boot each agent prints its address. Paste them into `.env`:
   `LIBRARIAN_ADDRESS`, `RECOVERY_ADDRESS` (and `LOGISTICS_ADDRESS` once Dev 4
   shares theirs), then restart the Orchestrator.
   *(Seeds are fixed, so addresses are stable across restarts.)*
2. Connect each agent's mailbox to Agentverse (the link is printed on boot /
   via the Agentverse Mailroom), and paste the matching file from `readmes/`
   into each agent's **Overview** tab. The Innovation Lab badge is already at
   the top of each README.
3. Verify with the **"Chat with Agent"** button on Agentverse, then through a
   public **ASI:One** chat session.

Smoke-test a deployed agent from the terminal:

```bash
ORCHESTRATOR_ADDRESS=agent1q... python send_dump.py
```

## How it satisfies the track requirements

| Requirement | Where |
|---|---|
| uAgents framework | all three agents |
| Agent Chat Protocol (handles `Start`/`Text`/`End` session, sends `ChatAcknowledgement`) | `agents/common/chat.py` + each agent's handler |
| `agent.include(chat_proto, publish_manifest=True)` | bottom of each agent file |
| Register ≥1 agent on Agentverse | `mailbox=True` on every agent |
| Discoverable + usable via ASI:One | Orchestrator (+ each worker) with README |
| Primary workflow w/o custom frontend | full loop runs in a chat session |
| Multi-step planning / orchestration (bonus) | Orchestrator fan-out/fan-in |
| README w/ agent name + address + Innovation Lab badge | `readmes/*.md` |
| Real reasoning via Claude (Anthropic) | `agents/common/claude.py` |

## Models

Set in `.env`. Defaults match the build plan's cost/latency choices:
`CLASSIFY_MODEL=claude-haiku-4-5` (fast splitter) and
`SYNTHESIS_MODEL=claude-sonnet-4-6` (overtraining reasoning). Both use
structured outputs so the JSON is schema-valid — no fragile parsing. Override
either in `.env` if you want a different model.

## Integrating with the rest of the team

- **Dev 2 (data/RAG):** the agents call `POST /entries`, `GET /entries`,
  `GET /metrics`, `POST /recovery_flags`. Point `BACKEND_URL` at the real
  service when it's up; the contract matches `mock_backend.py`.
- **Dev 4 (Logistics/Scout):** share your Logistics agent address →
  `LOGISTICS_ADDRESS` in `.env`. The Orchestrator/Librarian forward tournament
  notes to it over the chat protocol.

## Submission checklist (track)

- [ ] Public ASI:One shared chat session URL (full workflow)
- [ ] Agentverse profile URL(s) for the agent(s)
- [ ] Public GitHub repo with this runnable code
- [ ] 3–5 min demo video
- [ ] Problem + target-user write-up
