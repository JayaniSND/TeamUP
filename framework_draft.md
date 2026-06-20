# BASELINE — Build Plan

**A performance journal for self-managed individual-sport athletes. A notebook on the surface, an agent network underneath.**

Tennis first. The athlete brain-dumps after practice or a match — voice, text, or a photo of their paper notebook — and the system transcribes it, understands it, files each piece into the right section automatically, surfaces progress graphs, answers questions about their own history, flags overtraining, finds their next tournament, and drops it on their calendar.

The journal is the face. The autonomous agent layer underneath is the engineering story — and the Fetch.ai prize.

> **Pitch line:** the notebook the greatest endurance athletes keep by hand, except it organizes itself and acts on what it reads.

---

## 1. System architecture

One orchestrator + four worker agents, all built on Fetch.ai's uAgents framework, communicating over the standardized chat protocol.

```
                         ┌─────────────────────────┐
   voice / text / image  │      Next.js client     │
   ───────────────────►  │  (record, dashboard)    │
                         └───────────┬─────────────┘
                                     │ REST
                         ┌───────────▼─────────────┐
                         │   FastAPI backend       │
                         │  - auth, file upload    │
                         │  - data + RAG endpoints │
                         │  - deterministic        │
                         │    orchestrator         │
                         └───────────┬─────────────┘
                                     │ chat protocol (uAgents)
        ┌────────────┬───────────────┼───────────────┬─────────────┐
        ▼            ▼               ▼               ▼             ▼
   ┌─────────┐ ┌───────────┐  ┌────────────┐  ┌───────────┐  ┌─────────┐
   │Librarian│ │ Recovery  │  │ Logistics  │  │  Scout    │  │ASI:One  │
   │(Claude) │ │ (Claude)  │  │(GCal+web)  │  │(Browser-  │  │ router  │
   │classify │ │ flag      │  │ find + book│  │ base)     │  │(bonus)  │
   │+ route  │ │ overtrain │  │ tournament │  │ opponent  │  │         │
   └────┬────┘ └─────┬─────┘  └─────┬──────┘  └────┬──────┘  └─────────┘
        │            │              │              │
        ▼            ▼              ▼              ▼
   ┌──────────────────────────────────────────────────────┐
   │   Postgres (structured sections)  +  Redis (vectors) │
   └──────────────────────────────────────────────────────┘
```

**Key design decision — deterministic orchestration, not LLM-routed.** ASI:One's marketplace routing is non-deterministic (it ranks agents and may not pick yours). So the *live demo path* is a deterministic orchestrator in the FastAPI backend that calls the right uAgent directly via the chat protocol. The agents are still registered on Agentverse (with READMEs) for discoverability, and ASI:One finding your agent is shown as a **bonus clip**, never the critical path.

### The five agents

| Agent | Job | Fires when | Owner |
|---|---|---|---|
| **Orchestrator** | Receives raw dump, routes to worker(s) | Any submission | Dev 3 |
| **Librarian / Parser** | Classify content → write to section + vector store | Every input | Dev 3 |
| **Recovery** | Read injury/fitness logs, flag overtraining risk | Fitness/injury entry | Dev 3 |
| **Logistics** | Find next tournament, write to Google Calendar | Tournament mentioned | Dev 4 |
| **Scout** | Web-search opponent's recent matches, surface patterns | Match logged | Dev 4 |

---

## 2. Tech stack (mapped to sponsor prizes)

| Layer | Tool | Prize |
|---|---|---|
| Frontend | Next.js + Tailwind + shadcn/ui (Vercel) | — |
| API backend | FastAPI (Python — same runtime as uAgents) | — |
| Agents | **Fetch.ai uAgents**, hosted on **Agentverse** | **Fetch.ai (co-host)** |
| User-facing agentic LLM | **ASI:One** (`api.asi1.ai/v1`, OpenAI-compatible, model `asi1`) | **Fetch.ai** |
| Reasoning inside agents (classify, RAG synthesis) | **Claude API** (`claude-haiku-4-5` for classify, `claude-sonnet-4-6` for synthesis) | **Anthropic** |
| Voice → text | **Deepgram** | **Deepgram** |
| Vector store + cache | **Redis** (RediSearch vector index) | **Redis** |
| Structured data | Postgres (Supabase) | — |
| Tournament/opponent scraping | **Browserbase** | **Browserbase** |
| Calendar | Google Calendar API (free, 1M req/day) | — |
| Workflow orchestration | **Orkes Conductor** *(stretch only)* | **Orkes** |

**Double-dip:** Claude runs *inside* the uAgents for actual reasoning (Anthropic prize), ASI:One sits on top as the agentic router (Fetch.ai prize). Both sponsors get a genuine, defensible integration.

---

## 3. The demo loop (one continuous flow)

> Athlete records: *"Worked on serves today, knee was sore after, got a tournament in San Jose in two weeks."*
>
> 1. **Deepgram** transcribes the voice clip
> 2. **Librarian** (Claude) splits it: serve work → `coaching`, knee → `injury_log`, San Jose → `logistics`
> 3. **Recovery** sees recurring knee soreness across recent entries → **flags overtraining**
> 4. **Logistics** finds the San Jose tournament (Browserbase) → **adds it to Google Calendar**
> 5. Dashboard updates live; athlete asks chat *"how's my serve been trending?"* → RAG over past entries → **answer + graph**

Four agents visibly cooperating off a single sentence. Build the demo around hitting this loop end-to-end, then make it pretty.

---

## 4. Repo + environment setup (hour 0)

Monorepo, three deployables:

```
baseline/
├── web/            # Next.js (Dev 1 — out of scope for this doc)
├── api/            # FastAPI backend  (Dev 2)
│   ├── main.py
│   ├── db/         # schema, migrations
│   ├── rag/        # embeddings, retrieval
│   └── orchestrator.py
├── agents/         # uAgents          (Dev 3, Dev 4)
│   ├── librarian.py
│   ├── recovery.py
│   ├── logistics.py
│   ├── scout.py
│   └── common/     # chat protocol helpers, schemas
└── .env.example
```

`.env` keys everyone needs locally:

```
ANTHROPIC_API_KEY=          # console.anthropic.com
ASI_ONE_API_KEY=            # asi1.ai/dashboard/api-keys
DEEPGRAM_API_KEY=           # console.deepgram.com
BROWSERBASE_API_KEY=        # browserbase.com
BROWSERBASE_PROJECT_ID=
REDIS_URL=                  # Redis Cloud free tier (RediSearch enabled)
DATABASE_URL=               # Supabase Postgres
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=
```

**First 30 minutes, do these in parallel and commit a green skeleton:**
- Dev 2: FastAPI boots, `/health` returns 200, Supabase + Redis connect.
- Dev 3: one uAgent runs locally, registers on Agentverse, echoes a chat message.
- Dev 4: each external API authenticates with a one-line smoke test (Deepgram transcribes a sample wav, GCal lists calendars, Browserbase opens a page).

Lock the API contract (Section 5) before anyone writes real logic. That's what lets you work in parallel without merge hell.

---

## 5. API contract (lock this first)

The backend exposes these; agents and frontend code against them.

| Method | Route | Body / params | Returns |
|---|---|---|---|
| `POST` | `/ingest` | `{user_id, kind: voice\|text\|image, payload}` | `{entry_ids: [...], sections: [...]}` |
| `POST` | `/entries` | `{user_id, section, text, meta}` | `{entry_id}` |
| `GET` | `/entries` | `?user_id&section&limit` | `[{entry_id, section, text, ts, meta}]` |
| `POST` | `/chat` | `{user_id, question}` | `{answer, sources: [entry_id], chart?}` |
| `GET` | `/progress` | `?user_id&metric` | `[{ts, value}]` (for graphs) |
| `GET` | `/calendar` | `?user_id` | `[{title, start, end, source}]` |

`section` enum (single source of truth, share as a constant across all three repos):

```python
SECTIONS = ["performance", "injury_log", "coaching", "energy_nutrition", "logistics", "training"]
```

---

## 6. Dev 2 — Data + RAG layer

**You own the spine. Everyone depends on your endpoints, so ship the contract first and stub returns before logic is real.**

### Tasks
1. **Postgres schema** (Supabase). Minimal:
   ```sql
   users(id, name, sport, goals jsonb)
   entries(id, user_id, section, text, ts, meta jsonb)
   metrics(id, user_id, name, value, ts)          -- miles, serve speed, recovery score
   calendar_events(id, user_id, title, start, end, source)
   ```
2. **Embeddings + Redis vector store.** On every new entry, embed the text and upsert into a RediSearch vector index keyed by `user_id`. Use any embedding model (OpenAI `text-embedding-3-small` or a local sentence-transformer — keep it cheap and fast). Store `entry_id` + `section` as metadata so retrieval can filter by section.
3. **RAG retrieval + `/chat`.** Given a question: embed it, KNN over the user's vectors (optionally filtered by section the question implies), pass top-k entries to `claude-sonnet-4-6` as context, return a grounded answer + the `entry_id`s used as `sources`. If the question is trend-shaped ("how's my serve trending"), also pull the relevant `metrics` rows and return a `chart` payload.
4. **`/progress`** endpoint — straight query over `metrics`, returns time series for the graphs.
5. **`/ingest`** — accept text directly; for voice/image, call Dev 4's transcription/OCR helpers, then hand the resulting text to the orchestrator which invokes the Librarian. Return the created `entry_ids` + which `sections` they landed in.

### Done-when
- `/chat` answers a question grounded in seeded entries with correct `sources`.
- A new entry is searchable via vector KNN within one request cycle.
- `/progress` returns a clean series the frontend can plot.

### Redis prize angle
Use Redis for **both** the vector index (RediSearch) **and** caching expensive lookups (tournament search results, embeddings of repeated queries). Mention both uses in the submission — it reads as deliberate, not incidental.

---

## 7. Dev 3 — Agent Architect (Fetch.ai prize owner)

**Most prize-critical seat. Your deliverable is real uAgents communicating over the chat protocol and registered on Agentverse — that's the literal thing Fetch.ai judges score.**

### Tasks
1. **uAgents scaffolding.** Install `uagents`. Stand up the Orchestrator, Librarian, and Recovery agents, each with `mailbox=True` so they're reachable through Agentverse. Wire the chat protocol on each.
2. **Chat protocol wiring.** Use `uagents_core.contrib.protocols.chat` — handle `ChatMessage`, send `ChatAcknowledgement`, reply with `ChatMessage`. This is the inter-agent comms judges look for. Verify with the "Chat with Agent" button on Agentverse before integrating anything else.
3. **Librarian agent.** Receives a raw dump, calls `claude-haiku-4-5` to split it into `{section, text}` entries (JSON-only system prompt), writes each via Dev 2's `/entries`, and forwards injury/fitness entries to Recovery and tournament entries to Logistics.
4. **Recovery agent.** On an injury/fitness entry, pull the user's recent `injury_log` + `metrics` from Dev 2, ask Claude whether there's an overtraining pattern (e.g. same body part sore 3+ sessions, or training volume spike), and return a flag the dashboard surfaces.
5. **Agentverse registration + README.** Each agent needs a README.md in its Overview tab — that's what makes it discoverable by ASI:One. Write one per agent (handle, description, what it does).
6. **ASI:One bonus path.** Stand up an ASI:One-compatible entry agent so a natural-language query through ASI:One can reach your Librarian. Record a short clip of it working. Keep it **off** the critical demo path.

### Librarian skeleton (verify exact imports against current uAgents docs — the API moves)

```python
from datetime import datetime
from uuid import uuid4
import json, os, requests
import anthropic
from uagents import Agent, Protocol, Context
from uagents_core.contrib.protocols.chat import (
    ChatMessage, ChatAcknowledgement, TextContent, chat_protocol_spec,
)

SECTIONS = ["performance", "injury_log", "coaching",
            "energy_nutrition", "logistics", "training"]

agent = Agent(name="librarian", seed="librarian-secret-seed",
              port=8001, mailbox=True)
chat_proto = Protocol(spec=chat_protocol_spec)
claude = anthropic.Anthropic()                       # reads ANTHROPIC_API_KEY
API = os.environ["BACKEND_URL"]                      # Dev 2's FastAPI

SYS = (f"Split an athlete's journal dump into entries. Return ONLY a JSON "
       f"list of objects {{\"section\", \"text\"}}; section ∈ {SECTIONS}. "
       f"No prose, no code fences.")

@chat_proto.on_message(ChatMessage)
async def handle(ctx: Context, sender: str, msg: ChatMessage):
    text = "".join(c.text for c in msg.content if isinstance(c, TextContent))
    await ctx.send(sender, ChatAcknowledgement(
        timestamp=datetime.utcnow(), acknowledged_msg_id=msg.msg_id))

    resp = claude.messages.create(
        model="claude-haiku-4-5-20251001", max_tokens=1024,
        system=SYS, messages=[{"role": "user", "content": text}])
    entries = json.loads(resp.content[0].text)

    for e in entries:
        requests.post(f"{API}/entries", json={
            "user_id": ctx.storage.get("user_id"),
            "section": e["section"], "text": e["text"], "meta": {}})
        # forward to specialist agents
        if e["section"] == "injury_log":
            await ctx.send(RECOVERY_ADDR, ChatMessage(
                timestamp=datetime.utcnow(), msg_id=uuid4(),
                content=[TextContent(type="text", text=e["text"])]))
        if e["section"] == "logistics":
            await ctx.send(LOGISTICS_ADDR, ChatMessage(
                timestamp=datetime.utcnow(), msg_id=uuid4(),
                content=[TextContent(type="text", text=e["text"])]))

    await ctx.send(sender, ChatMessage(
        timestamp=datetime.utcnow(), msg_id=uuid4(),
        content=[TextContent(type="text", text=f"Filed {len(entries)} entries.")]))

agent.include(chat_proto, publish_manifest=True)
if __name__ == "__main__":
    agent.run()
```

ASI:One call pattern, for the bonus router (OpenAI-compatible):

```python
from openai import OpenAI
asi = OpenAI(base_url="https://api.asi1.ai/v1", api_key=os.environ["ASI_ONE_API_KEY"])
resp = asi.chat.completions.create(model="asi1",
        messages=[{"role": "user", "content": user_query}])
```

### Done-when
- Librarian + Recovery run, register on Agentverse, and pass a `ChatMessage` between each other.
- A raw dump in → correctly-sectioned entries written to Dev 2's DB.
- READMEs published; one ASI:One clip recorded.

---

## 8. Dev 4 — Integrations + Logistics/Scout agents

**You own everything that touches the outside world. Mostly self-contained, so you can move fast in parallel.**

### Tasks
1. **Deepgram voice → text.** Helper `transcribe(audio_bytes) -> str` for `/ingest` voice path. Use a prerecorded transcription call with a current model (e.g. Nova). Expose it so Dev 2 can call it inside `/ingest`.
2. **Image OCR (notebook photo).** Simpler than it sounds — pass the image straight to `claude-sonnet-4-6` with vision and ask it to transcribe the handwritten page to text. No separate OCR service needed.
3. **Google Calendar integration.** OAuth once per user; helper `add_event(user_id, title, start, end)` using `events.insert`. Free tier is plenty (1M req/day). This is what Logistics calls.
4. **Browserbase tournament/opponent search.** Helper `find_tournament(location, date_window) -> {name, dates, venue, url}` and `scout_opponent(name) -> [recent_matches]`. Drive a headless browser session to a tennis tournament/results site, extract structured results. Cache hits in Redis (coordinate key format with Dev 2).
5. **Logistics agent (uAgent).** On a tournament entry from Librarian: `find_tournament` → `add_event` to GCal → return the event so it shows on the dashboard calendar.
6. **Scout agent (uAgent).** On a logged match: `scout_opponent` → summarize patterns with Claude → write a `coaching` entry.
7. **Weekly fitness plan (stretch).** Generate a weekly plan from goals + recent load with Claude, merge into GCal.

### Done-when
- Voice clip → transcript → sectioned entries (whole chain with Dev 2/Dev 3).
- "Tournament in San Jose in two weeks" → real-ish event on the demo Google Calendar.
- Browserbase returns at least one real tournament/opponent record live.

---

## 9. Build timeline + checkpoints

| Hour | Target |
|---|---|
| 0–1 | Repo, `.env`, API contract locked, every external API smoke-tested green |
| 1–4 | Dev 2 DB + `/entries` + `/ingest` stub; Dev 3 two agents echoing over chat protocol; Dev 4 Deepgram + GCal helpers working |
| 4–8 | Librarian classifies for real → writes entries; Dev 2 vector store + `/chat` returning grounded answers; Dev 4 Logistics agent hits GCal |
| 8–12 | Full demo loop wired end-to-end (voice → sectioned → Recovery flag → GCal event → chat answer). **This is the hard checkpoint — everything after is polish.** |
| 12–18 | Recovery + Scout agents real; progress graphs populated; Agentverse READMEs + ASI:One bonus clip |
| 18–24 | Polish demo, seed a believable athlete history, record backup video of the loop |
| 24–36 | *Only if green:* Orkes orchestration, second sport mention, slide deck |

If you're not at the hour-12 checkpoint with the loop closed, cut scope, not polish.

---

## 10. Scope discipline

**Cut entirely (stub or don't mention):**
- Hotel/flight booking — real booking APIs need approval + auth you don't have time for. "Future agent."
- Nutrition data model, psychologist agent, player-to-player scheduling (no users exist yet — chicken-and-egg).

**Stretch only (touch after hour 24, if green):**
- Orkes Conductor orchestration.
- Sport-agnosticism — build and demo tennis; *say* in one sentence "the agent layer generalizes to badminton, swimming, track."
- Weekly fitness plan generation.

**Never let the demo depend on:** ASI:One's marketplace routing, live Browserbase scraping with no fallback (cache a known-good result), or any unauthenticated booking flow.

---

## 11. Prize-targeting checklist

| Sponsor | What must be true at submission |
|---|---|
| **Fetch.ai** | ≥2 real uAgents on Agentverse, chat protocol comms, READMEs published, ASI:One can reach one agent |
| **Anthropic** | Claude does the real reasoning (classification + RAG synthesis), shown in the loop |
| **Deepgram** | Voice brain-dump transcribed live in the demo |
| **Redis** | RediSearch vector index **and** caching, both called out |
| **Browserbase** | Live (or cached-from-live) tournament/opponent scrape |
| **Orkes** | *(stretch)* Conductor orchestrating the agent workflow |

---

## 12. Demo script (90 seconds)

1. "Independent athletes manage everything a team's staff would — alone." (problem, 10s)
2. Record the voice dump live. (10s)
3. Watch the dashboard: entry splits into Coaching + Injury + Logistics; Recovery flag pops; calendar event appears. (30s)
4. Ask the chat "how's my serve trending?" → grounded answer + graph. (20s)
5. "Five autonomous agents on Fetch.ai, Claude reasoning, Deepgram voice — off one sentence." Show the Agentverse agent list. (20s)
