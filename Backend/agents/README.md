# BASELINE — Agent Layer

The Fetch.ai-facing half of BASELINE, the **sports analytics dashboard that
builds itself from an athlete's logs**: real **uAgents** that talk over the
standardized **Agent Chat Protocol**, registered on **Agentverse**, reachable
through **ASI:One**, with **Claude** doing the reasoning inside them.

> Track: UC Berkeley AI Hackathon 2026 — Fetch.ai. See [`framework.md`](../../framework.md)
> for the full product spec. This folder is the agent-layer deliverable.

## What's here

```
Backend/
├── agents/
│   ├── orchestrator.py     # ASI:One entry point — conducts the whole loop
│   ├── librarian.py        # Parser: classify a dump → file into sections
│   ├── recovery.py         # fatigue / soreness / overtraining (wellness)
│   ├── performance.py      # win/loss + skill trends
│   ├── sponsorship.py      # brand fit + draft cold email (approval-gated)
│   └── common/
│       ├── config.py       # SECTIONS, section→agent map, models, addresses
│       ├── chat.py         # chat-protocol helpers (+ session content)
│       ├── claude.py       # classify + recovery/performance/sponsorship reasoning
│       └── backend_client.py  # async client for the data backend's FastAPI
├── readmes/                # Agentverse "Overview" READMEs (Innovation Lab badge)
├── mock_backend.py         # data backend stand-in: full schema + dashboard routes, seeded
├── run_local.py            # one-command OFFLINE end-to-end test (Bureau)
├── send_dump.py            # message a deployed/mailbox agent and print replies
├── asi_ping.py             # optional ASI:One probe for the bonus clip
├── requirements.txt
└── .env.example
```

Logistics + Coaching/Chat agents live elsewhere in the project (see
[`framework.md`](../../framework.md) §6).

## Sections

```
training · performance · match_results · recovery · coaching ·
logistics · sponsorship · goals · media_notes
```

## Architecture

```
            (ASI:One / Agentverse "Chat with Agent")
                          │  chat protocol
                          ▼
                 ┌──────────────────┐
                 │   Orchestrator   │  classify → route → correlate → answer
                 └───┬───────┬───┬──┘
            chat ▼   │       │   ▼ chat
         ┌──────────┐│       │┌──────────────┐
         │ Librarian││       ││  Logistics   │ (external)
         │ (Claude) ││       │└──────────────┘
         └────┬─────┘▼       ▼
              │ ┌─────────┐ ┌────────────┐ ┌──────────────┐
              │ │Recovery │ │Performance │ │ Sponsorship  │
              │ │(Claude) │ │ (Claude)   │ │  (Claude)    │
              │ └────┬────┘ └─────┬──────┘ └──────┬───────┘
              └──────┴───────┬────┴───────────────┘
                             ▼  REST
            Data backend FastAPI (entries, metrics, matches, agent_outputs, …)
```

The Orchestrator is the single agent a user talks to. It delegates
classification to the Librarian, then — based on which sections appear —
triggers Recovery / Performance / Sponsorship / Logistics, correlates their
replies, and composes one answer. Each worker is **also independently usable**
through ASI:One on its own.

## Setup

```bash
cd Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then fill in ANTHROPIC_API_KEY
```

## Run it locally (offline, one command)

```bash
# terminal 1 — the data backend stand-in (seeded athlete history)
uvicorn mock_backend:app

# terminal 2 — all agents + a test user, in one process
python run_local.py
```

The demo dump is classified into sections, the win is picked up by Performance,
the seeded knee history triggers a Recovery flag, the win triggers a Sponsorship
draft, and the tournament note routes to Logistics — all printed as chat replies.

## Run it as real Agentverse agents (submission path)

One terminal each (workers first, so you can copy their addresses):

```bash
python -m agents.recovery        # prints RECOVERY address
python -m agents.performance     # prints PERFORMANCE address
python -m agents.sponsorship     # prints SPONSORSHIP address
python -m agents.librarian       # prints LIBRARIAN address
python -m agents.orchestrator    # prints ORCHESTRATOR address
```

1. Paste each printed address into `.env` (`LIBRARIAN_ADDRESS`,
   `RECOVERY_ADDRESS`, `PERFORMANCE_ADDRESS`, `SPONSORSHIP_ADDRESS`, and
   `LOGISTICS_ADDRESS` once the logistics agent address is available), then restart the Orchestrator.
   Seeds are fixed, so addresses are stable across restarts.
2. Connect each agent's mailbox to Agentverse and paste the matching file from
   `readmes/` into its **Overview** tab (the Innovation Lab badge is already at
   the top of each).
3. Verify with **"Chat with Agent"** on Agentverse, then a public **ASI:One**
   chat session.

Smoke-test a deployed Orchestrator from the terminal:

```bash
ORCHESTRATOR_ADDRESS=agent1q... python send_dump.py
```

## How it satisfies the track requirements

| Requirement | Where |
|---|---|
| uAgents framework | all five agents |
| Agent Chat Protocol (`Start`/`Text`/`End` session, `ChatAcknowledgement`) | `agents/common/chat.py` + each handler |
| `agent.include(chat_proto, publish_manifest=True)` | bottom of each agent file |
| Register ≥1 agent on Agentverse | `mailbox=True` on every agent |
| Discoverable + usable via ASI:One | Orchestrator (+ each worker) with README |
| Primary workflow w/o custom frontend | full loop runs in a chat session |
| Multi-step planning / orchestration (bonus) | Orchestrator fan-out/fan-in |
| README w/ agent name + address + Innovation Lab badge | `readmes/*.md` |
| Real reasoning via Claude (Anthropic) | `agents/common/claude.py` |

## Models

Set in `.env`. Defaults: `CLASSIFY_MODEL=claude-haiku-4-5` (fast splitter) and
`SYNTHESIS_MODEL=claude-sonnet-4-6` (recovery/performance/sponsorship reasoning).
All use structured outputs, so the JSON is schema-valid — no fragile parsing.

## Integrating with the team

- **Data backend (data/RAG):** agents call `POST /entries`, `GET /entries`,
  `GET /metrics`, `GET /match_results`, `GET /training_sessions`,
  `GET /recovery_logs`, `GET /athlete_profile`, `POST /agent_outputs`,
  `POST /sponsorship_opportunities`. Point `BACKEND_URL` at the real service when
  up; the contract matches `mock_backend.py`.
- **Logistics/Scout:** share the Logistics agent address →
  `LOGISTICS_ADDRESS`. The Orchestrator/Librarian forward schedule/tournament
  notes to it over the chat protocol.

## Submission checklist (track)

- [ ] Public ASI:One shared chat session URL (full workflow)
- [ ] Agentverse profile URL(s) for the agent(s)
- [ ] Public GitHub repo with this runnable code
- [ ] 3–5 min demo video
- [ ] Problem + target-user write-up
