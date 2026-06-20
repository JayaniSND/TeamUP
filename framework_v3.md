# BASELINE — Build Framework

**A personal sports analytics OS for individual athletes — built from their own notebooks, voice logs, training history, game results, recovery patterns, and sponsorship potential.**

This is not "a journal with AI." The stronger framing:

> **An AI sports analytics dashboard that builds itself from an athlete's personal logs.**

The notebook photo, voice dump, and text input are the *input methods*. The
dashboard is the *product*. The autonomous agents are the *engineering story*
(and the Fetch.ai prize).

Pitch: *"It turns messy athlete logs into a live sports analytics dashboard."*
Shortest: *"The athlete dashboard that builds itself from your notebooks and voice logs."*

> Supersedes `framework_draft.md`. Track: **UC Berkeley AI Hackathon 2026 — Fetch.ai**.

---

## 0. Stack & track alignment

| Layer | Tool | Prize / reason |
|---|---|---|
| Frontend dashboard | Next.js + React + Tailwind + shadcn/ui | — |
| API backend + RAG | FastAPI (same runtime as uAgents) | — |
| Agents | **Fetch.ai uAgents** on **Agentverse**, **Agent Chat Protocol** | **Fetch.ai (co-host)** |
| Agentic entry point | **ASI:One** (`api.asi1.ai/v1`, model `asi1`) | **Fetch.ai** |
| Reasoning inside agents | **Claude** (`claude-haiku-4-5` classify, `claude-sonnet-4-6` synthesis) | **Anthropic** |
| Voice → text | **Deepgram** | **Deepgram** |
| Photo → text | **Claude vision** (no separate OCR) | **Anthropic** |
| Vector store + cache | **Redis** (RedisVL + LangCache + Agent Memory) | **Redis** |
| Structured data | Postgres (Supabase) | — |
| Tournament/brand search | **Browserbase** | **Browserbase** |
| Calendar | Google Calendar API | — |
| Error monitoring + observability | **Sentry** | **Sentry** |

**Fetch.ai track requirements (must hold at submission):**

- Agents built on **uAgents** and registered on **Agentverse** (`mailbox=True`).
- Implement the **Agent Chat Protocol** (`uagents_core.contrib.protocols.chat`):
  handle `StartSessionContent` / `TextContent` / `EndSessionContent`, send
  `ChatAcknowledgement`, and `agent.include(chat_proto, publish_manifest=True)`.
- At least one agent **discoverable and directly usable through ASI:One**.
- The **primary workflow completes without a custom frontend** (works in a chat
  session). The dashboard is the polished surface on top, not a dependency for
  the agent demo.
- Each agent's Agentverse **Overview** README includes its name, address, and the
  **Innovation Lab** badge.
- Bonus: multi-agent orchestration, real-time data, payment protocol.

---

## 1. Target user

**Individual, self-managed athletes** across sports — tennis, swimming, running,
badminton, track, golf, fighters, and others. They manage alone what a team's
staff normally would: training notes, match results, recovery/soreness, travel
and logistics, performance trends, sponsorship, goals, schedule, coaching.

---

## 2. Core product flow

```txt
Notebook photo / voice dump / text input
        ↓ preprocessing (Claude vision / Deepgram)
Parser / Librarian Agent  (classify → sections)
        ↓
Specialized Agents  (Recovery, Performance, Logistics, Sponsorship)
        ↓
Database  (Postgres)
        ↓
Sports analytics dashboard  (reads DB only)
        ↓
AI chat + section-specific controls
```

Every dashboard component is powered by DB data created or updated by agents.

---

## 3. Input types

1. **Notebook photo** → Claude vision → raw transcript → Parser → structured
   entries → dashboard. *Builds the athlete's history fast.*
2. **Voice dump** → Deepgram → raw transcript → Parser → entries → dashboard.
   *Fast daily logging; best for the live demo.*
3. **Text input** → Parser → entries. *Backup / demo fallback.*

All three converge on the same Parser pipeline; the frontend never cares which
input produced a row.

---

## 4. Sections (single source of truth)

Shared as a constant across backend, agents, and frontend.

```ts
SECTIONS = [
  "training",
  "performance",
  "match_results",
  "recovery",
  "coaching",
  "logistics",
  "sponsorship",
  "goals",
  "media_notes"
]
```

| Section | Purpose |
|---|---|
| `training` | Practice sessions, drills, training load, workout details |
| `performance` | Skill trends, stats, strengths/weaknesses, measurable improvements |
| `match_results` | Game/match results, opponents, scores, win/loss history |
| `recovery` | Soreness, fatigue, sleep, injury risk, wellness logs |
| `coaching` | AI coaching notes, tactical feedback, suggestions |
| `logistics` | Tournaments, travel, schedules, calendar, locations |
| `sponsorship` | Sponsor fit, brand opportunities, cold-email drafts, outreach status |
| `goals` | Short- and long-term athlete goals |
| `media_notes` | Social media, highlight clips, achievements, brand-facing notes |

---

## 5. Database schema (MVP)

```sql
users (
  id uuid primary key, name text, sport text, level text,
  location text, created_at timestamp
);

athlete_profiles (
  id uuid primary key, user_id uuid references users(id),
  age int, height text, weight text, dominant_side text, team_or_club text,
  goals jsonb, strengths jsonb, weaknesses jsonb, injury_history jsonb
);

raw_inputs (
  id uuid primary key, user_id uuid references users(id),
  input_type text,            -- photo | voice | text
  raw_text text, file_url text, created_at timestamp
);

entries (                      -- core flexible table; Parser writes here first
  id uuid primary key, user_id uuid references users(id),
  raw_input_id uuid references raw_inputs(id),
  section text, title text, text text, tags text[],
  confidence float, metadata jsonb,
  embedded boolean default false,  -- set true once RedisVL embedding stored
  created_at timestamp
);

training_sessions (
  id uuid primary key, user_id uuid references users(id),
  date date, sport text, session_type text, duration_minutes int,
  intensity int, focus_area text, notes text, created_at timestamp
);

match_results (
  id uuid primary key, user_id uuid references users(id),
  date date, opponent text, event_name text,
  result text,                -- win | loss | draw
  score text, key_stats jsonb, notes text, created_at timestamp
);

recovery_logs (
  id uuid primary key, user_id uuid references users(id),
  date date, soreness_level int, fatigue_level int, sleep_hours float,
  injury_area text, pain_level int, risk_level text, notes text, created_at timestamp
);

metrics (
  id uuid primary key, user_id uuid references users(id),
  metric_name text, metric_value float, unit text, date date,
  source_entry_id uuid references entries(id)
);

calendar_events (
  id uuid primary key, user_id uuid references users(id),
  title text, event_type text,  -- game | tournament | training | travel | recovery
  start_time timestamp, end_time timestamp, location text, source text, metadata jsonb
);

sponsorship_opportunities (
  id uuid primary key, user_id uuid references users(id),
  brand_name text, category text, contact_email text,
  fit_score float, reason text,
  status text,                -- suggested | drafted | sent | replied | rejected
  draft_email text, created_at timestamp
);

agent_outputs (                -- visible agent-generated insights
  id uuid primary key, user_id uuid references users(id),
  agent_name text, section text, summary text, severity text,
  recommended_action text, related_entry_ids uuid[], created_at timestamp
);
```

`agent_outputs` is the dashboard's "AI insight cards / alerts / next actions"
feed — every specialist agent writes a row here.

**Product rule on recovery:** frame as **wellness and self-management**, not
medical diagnosis.

---

## 6. Agents

Built on Fetch.ai uAgents, talking over the Agent Chat Protocol, with Claude
doing the reasoning. The **Orchestrator** is the ASI:One entry point and
conducts the loop; each specialist is also independently usable via ASI:One.

### Ownership (team split)

| Agent | Job | Owner |
|---|---|---|
| **Orchestrator** | Single ASI:One entry point; routes a dump to the workers, correlates replies, composes one answer | Dev 3 |
| **Parser / Librarian** | Classify raw input → write `entries` (and structured tables) | Dev 3 |
| **Recovery** | Detect fatigue/soreness/overtraining patterns → `agent_outputs` | Dev 3 |
| **Performance** | Summarize win/loss + skill trends from matches/metrics → `agent_outputs` | Dev 3 |
| **Sponsorship** | Find brand fit + draft cold email (approval-gated) → `sponsorship_opportunities` | Dev 3 |
| **Logistics** | Tournaments/travel/calendar (Browserbase + Google Calendar) | Dev 4 |
| **Coaching / Chat** | RAG over the athlete's DB to answer questions (`/chat`) | Dev 2 |

### 6.1 Parser / Librarian
Turns messy input into structured entries.

```txt
in:  "Felt tired today. Lost 6-4, 6-3. Serve was weak. Knee pain again. Tournament next Saturday."
out: [
  {"section":"recovery","text":"Felt tired today. Knee pain again."},
  {"section":"match_results","text":"Lost 6-4, 6-3."},
  {"section":"performance","text":"Serve was weak."},
  {"section":"logistics","text":"Tournament next Saturday."}
]
```
Writes `raw_inputs`, `entries`, and optionally `training_sessions` /
`match_results` / `recovery_logs` / `calendar_events`.

### 6.2 Recovery
Reads `recovery_logs`, `training_sessions`, `entries`, `metrics`. Two modes:

**Passive (fires on every new entry):** pulls the last 14 days of entries across
all sections and sends them to Claude with a sports medicine prompt — *not* looking
for injury keywords, but for linguistic drift: serve descriptions shifting from
"explosive" to "muscling through", a body side described with increasing negativity,
load spikes with no rest language. Checks Agent Memory before running — if a
similar flag exists within 72 hours, skips to avoid duplicate alerts. Stores
finding (or "checked clean") in Agent Memory after every run.

**Chat-triggered:** athlete asks "how's my body been?" → reads Agent Memory for
prior findings → runs fresh analysis → returns grounded answer to chat.

Writes `agent_outputs` (+ `recovery_logs`, `metrics`).
Output: `{risk_level, severity, body_parts, summary, recommended_action}`.

> **Seeded data requirement:** load 12–14 fake entries with deliberate linguistic
> drift before demo day so the passive detection fires reliably on stage.

### 6.3 Performance
Reads `match_results`, `training_sessions`, `metrics`, `entries`. Summarizes
win/loss trend, strongest/weakest area, recent form, improvement suggestions.
Writes `agent_outputs`.

### 6.4 Logistics (Dev 4)
Reads `entries`, `calendar_events`, external tournament search, Google Calendar.
Outputs upcoming events, schedules, travel checklist, calendar adds.

**Browserbase integration:** two scraping tasks, both with cached fallbacks.

```python
from browserbase import Browserbase
bb = Browserbase(api_key=os.environ["BROWSERBASE_API_KEY"])

def scrape_tournaments(location: str, date_range: str) -> str:
    try:
        session = bb.sessions.create(project_id=os.environ["BROWSERBASE_PROJECT_ID"])
        # navigate to tournament finder → return raw page text
        # Claude extracts structured event data from raw text
    except Exception as e:
        sentry_sdk.capture_exception(e)
        return CACHED_TOURNAMENT_FALLBACK   # never let scraping kill the demo

def scrape_opponent(name: str) -> str:
    try:
        session = bb.sessions.create(project_id=os.environ["BROWSERBASE_PROJECT_ID"])
        # navigate to rankings / match history → return raw page text
    except Exception as e:
        sentry_sdk.capture_exception(e)
        return CACHED_OPPONENT_FALLBACK
```

> **Demo rule:** pre-scrape and cache one tournament result and one opponent card
> the night before. Live scraping is the happy path; cached result is the fallback.

### 6.5 Sponsorship
Reads `athlete_profiles`, `match_results`, `metrics`, `media_notes`, external
brand search. Outputs `{brand_name, category, fit_score, reason, draft_email}`.
**Approval-gated** — never auto-sends:
```txt
suggest sponsor → explain fit → draft email → user edits/approves → send
```
Writes `sponsorship_opportunities` (+ `agent_outputs`).

### 6.6 Coaching / Chat (Dev 2)
RAG over the whole DB (`entries`, `metrics`, `match_results`, `recovery_logs`,
`calendar_events`, `sponsorship_opportunities`, `agent_outputs`). Returns a
grounded answer + source entries + optional chart + recommended action.
Example questions: *"How has my serve been trending?"*, *"Am I training too much
this week?"*, *"Draft a sponsorship email based on my recent wins."*

---

## 6a. Routing flowchart — when each agent or RAG is called

Every athlete message enters the single chat interface. Claude reads the intent and routes to the right tool. Agents fire on **action-oriented** requests; RAG fires on **history-oriented** questions.

```
ATHLETE MESSAGE
        │
        ▼
  Claude reads intent
        │
        ├─── "log my practice / I trained / just finished..." ──► Parser / Librarian
        │         writes entries → embed pipeline → RedisVL
        │         background: Recovery + Performance + Logistics + Sponsorship
        │
        ├─── "how has my serve been / what patterns do you see..." ──► RAG (§6b)
        │         RedisVL KNN → Claude Coaching/Chat agent → answer + sources
        │
        ├─── "find me a tournament / book / schedule..." ──► Logistics agent
        │         Browserbase search → Google Calendar → confirmation
        │
        ├─── "research my opponent / tell me about [name]..." ──► Logistics / Scout
        │         Browserbase scrape → opponent card
        │
        ├─── "how's my body / am I overtrained / recovery..." ──► Recovery agent
        │         Agent Memory check → 14-day Postgres query → Claude analysis
        │         → Agent Memory store → agent_outputs write
        │
        ├─── "find sponsors / draft outreach email..." ──► Sponsorship agent
        │         approval-gated: suggest → draft → user approves → send
        │
        └─── "how am I performing / win-loss trend..." ──► Performance agent
                  match_results + metrics → Claude synthesis → agent_outputs
```

**Rule:** if the question requires searching *across weeks of unstructured history*
with no clear agent owner → RAG. If it requires an *action or a structured data
read* → the relevant agent.

---

## 6b. RAG pipeline (Coaching / Chat agent — Dev 2)

### Why RAG exists

Claude has no memory between API calls. Without RAG, `/chat` returns generic
answers with no knowledge of this athlete's history. RAG fetches the most
semantically relevant journal entries and hands them to Claude as context —
so answers are grounded in the athlete's *actual* logged data, not general
sports knowledge.

### What we retrieve

The athlete's own `entries` rows, embedded into RedisVL at write time. When the
athlete asks *"what patterns do you see in my energy before losses?"*, we retrieve
the top-8 most semantically similar entries across all sections — training logs,
recovery notes, coaching feedback — and bundle them into Claude's prompt. Semantic
search means *"first serve felt weak and I was muscling through it"* surfaces for
the query *"serve power"* even though the words don't match.

### The four steps

**Step 1 — Embed (at write time, inside `POST /entries`)**

Every new entry is embedded immediately before the endpoint returns.

```python
# runs inside POST /entries, before response
text  →  embedding_model(text)  →  [1024 floats]
Postgres INSERT  →  embedded = false
RedisVL store    →  entry:{uuid}  { entry_id, user_id, section, text, embedding }
Postgres UPDATE  →  embedded = true
```

Agents and the frontend never touch RedisVL. The embed pipeline is owned by
Dev 2 and runs as part of the ingest flow.

**Step 2 — Store (RedisVL index)**

```python
# one-time index creation at app startup
index fields:
  TextField("text")
  TextField("section")
  TextField("user_id")
  VectorField("embedding", "FLAT", { TYPE: FLOAT32, DIM: 1024,
                                      DISTANCE_METRIC: COSINE })
prefix: "entry:"
```

**Step 3 — Retrieve (at query time)**

```python
def retrieve(question: str, user_id: str, top_k: int = 8):
    q_embedding = embed(question)
    results = redis.ft("entries_idx").search(
        Query(f"(@user_id:{user_id})=>[KNN {top_k} @embedding $vec AS score]")
        .sort_by("score")
        .return_fields("entry_id","text","section","score")
        .dialect(2),
        query_params={"vec": q_embedding.tobytes()}
    )
    return results.docs
```

**Step 4 — Generate (Claude)**

```python
context = "\n\n".join([
    f"[{e.section.upper()}]\n{e.text}" for e in entries
])
prompt = f"""You are a sports performance analyst reviewing an athlete's journal.
Answer using ONLY the entries below. Be specific — quote what they actually wrote.
If entries lack enough information, say so.

JOURNAL ENTRIES:
{context}

QUESTION: {question}"""

response = claude.messages.create(
    model="claude-sonnet-4-6", max_tokens=1000,
    messages=[{"role":"user","content": prompt}]
)
return { "answer": response.content[0].text,
         "sources": [e.entry_id for e in entries] }
```

`sources` lets the frontend highlight exactly which entries Claude used.

### LangCache wrapper (Redis Iris)

Wraps Step 3–4. Semantically caches Claude responses so repeated or similar
questions don't trigger a full RAG + Claude call.

```python
@app.post("/chat")
async def chat(body: ChatRequest):
    cached = langcache.search(body.question, user_id=body.user_id)
    if cached:
        return cached                          # no embed, no Redis KNN, no Claude

    entries  = retrieve(body.question, body.user_id)
    result   = generate(body.question, entries)
    langcache.store(body.question, result, user_id=body.user_id)
    return result
```

### Agent Memory (Redis Iris — Recovery agent)

Recovery agent reads and writes Agent Memory before/after every analysis run.
Prevents duplicate alerts and gives Recovery continuity across sessions.

```python
# Recovery agent — before analysis
prior = agent_memory.search(f"recovery flag user:{user_id}")
if prior and prior[0].timestamp > now() - timedelta(hours=72):
    return   # already flagged recently, skip

# Recovery agent — after analysis
if finding.severity > threshold:
    agent_memory.store(finding)           # long-term continuity
    write_agent_output(finding)           # surfaces on dashboard
else:
    agent_memory.store(f"checked clean {today}")
```

### Redis tools used — judging summary

| Tool | Where used | Judging criterion |
|---|---|---|
| **RedisVL** | Vector search + KNN retrieval in RAG | Beyond caching — vector search |
| **LangCache** | Semantic response cache on `/chat` | Beyond caching — context retrieval |
| **Agent Memory** | Recovery agent continuity across runs | Beyond caching — agent memory |
| **Redis Cloud** | Hosts all of the above | Required qualifier |

README line for submission: *"We use RedisVL for semantic retrieval across the
athlete's journal, LangCache to avoid redundant Claude calls for similar questions,
and Redis Agent Memory so our Recovery agent builds a persistent picture of the
athlete's physical health over time — not just a 14-day snapshot."*

---

## 6c. Observability — Sentry

### Why Sentry / judging context

Sentry judges on **how the team worked under pressure**, not just what was built.
They want evidence of reliability thinking from day one: catching real bugs,
communicating around failures, and course-correcting fast. Add Sentry at **hour 0**
so it captures genuine errors throughout the build — not bolted on at hour 23.

### FastAPI backend setup

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

sentry_sdk.init(
    dsn=os.environ["SENTRY_DSN"],
    integrations=[FastApiIntegration(), SqlalchemyIntegration()],
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
    environment="hackathon",
    release="baseline@1.0.0"
)
```

Gives automatic error capture on every FastAPI route, DB query performance, and
request tracing with zero extra code.

### Agent monitoring — spans per agent run

```python
import sentry_sdk

def run_recovery_agent(user_id: str):
    with sentry_sdk.start_transaction(op="agent", name="Recovery"):
        with sentry_sdk.start_span(op="memory.read", description="Agent Memory check"):
            prior = agent_memory.search(f"recovery flag user:{user_id}")
        with sentry_sdk.start_span(op="db.query", description="fetch 14-day entries"):
            entries = fetch_recent_entries(user_id, days=14)
        with sentry_sdk.start_span(op="ai.inference", description="Claude linguistic analysis"):
            finding = claude_analyze(entries)
        with sentry_sdk.start_span(op="db.write", description="write agent_output"):
            write_agent_output(finding)
```

Sentry dashboard shows: "Recovery agent 3.2s — 0.1s memory read, 0.1s DB,
2.9s Claude, 0.1s write." Real observability per agent, not just global errors.

### RAG pipeline monitoring

```python
def retrieve(question: str, user_id: str):
    with sentry_sdk.start_span(op="vector.search", description="RedisVL KNN"):
        results = redis_knn_search(question, user_id)
    sentry_sdk.set_context("rag", {
        "question": question,
        "results_count": len(results),
        "top_score": results[0].score if results else None
    })
    return results
```

Zero-result RAG queries are captured with full context — easy to debug if the
embed pipeline missed entries.

### Browserbase error capture

Browserbase scraping failures are automatically caught and routed to the cached
fallback (see §6.4). Sentry captures the exception with location + fallback flag
so you know exactly when and why live scraping fell back.

### Next.js frontend

```bash
npx @sentry/wizard@latest -i nextjs
```

One command. Automatic error boundaries, session replay, and performance monitoring
on every page.

### Judging story — three things to do during the build

1. **Use Sentry as your error communication channel.** When something breaks,
   check Sentry first and share the trace link in team chat — not just "it's
   broken." This is the collaborative problem-solving they're judging.
2. **Document one real bug caught and fixed via Sentry** in the submission
   write-up. *"At hour 14, Sentry caught a silent embed pipeline failure —
   entries were inserting to Postgres but RedisVL store was failing without
   error. The span timing drop surfaced it. Fixed in 20 minutes."*
3. **Show the Sentry dashboard for 30 seconds in the demo video.** Every agent
   run visible, every RAG query traced, the one real bug caught. Almost nobody
   does this. Judges remember it.

---

## 7. Dashboard

A sports analytics **command center**, not a notes page.

**Top overview cards:** Weekly Load · Recovery Risk · Next Event · Recent Result
· Current AI Focus · Main Goal.

**Sections:** Overview · Training · Performance · Match Results · Recovery ·
Schedule/Logistics · Sponsorship · AI Chat.

**Section-specific AI actions** (small buttons per section):
- Training: Ask AI · Generate next week's plan · Explain load · Summarize 7 days
- Performance: Ask AI · Explain trend · Identify weakest area · Compare games
- Match Results: Ask AI · Analyze losses · Recent form · Patterns by opponent
- Recovery: Ask AI · Check overtraining risk · Explain soreness · Suggest rest day
- Logistics: Ask AI · Add to calendar · Travel checklist · Find tournament
- Sponsorship: Ask AI · Find matches · Draft email · Improve pitch · Mark contacted

---

## 8. API endpoints (lock first)

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/ingest` | Accept photo, voice, or text input |
| `POST` | `/entries` | Create structured entry |
| `GET` | `/entries` | Get entries by section (`?user_id&section&limit`) |
| `GET` | `/dashboard/overview` | Top dashboard summary |
| `GET` | `/dashboard/training` | Training dashboard data |
| `GET` | `/dashboard/performance` | Performance dashboard data |
| `GET` | `/dashboard/matches` | Match-result data |
| `GET` | `/dashboard/recovery` | Recovery dashboard data |
| `GET` | `/dashboard/logistics` | Schedule + calendar data |
| `GET` | `/dashboard/sponsorship` | Sponsorship opportunities |
| `POST` | `/chat` | Ask AI about athlete history |
| `POST` | `/agents/run` | Trigger a specific agent manually |
| `POST` | `/sponsorship/draft` | Generate cold-email draft |
| `POST` | `/calendar/add` | Add event to calendar |

Agent-support endpoints used by the agent layer: `GET /metrics`,
`GET /match_results`, `GET /training_sessions`, `GET /recovery_logs`,
`GET /athlete_profile`, `POST /agent_outputs`, `POST /recovery_logs`,
`POST /sponsorship_opportunities`.

### Contract examples

`/dashboard/overview`
```json
{
  "athlete": {"name":"Demo Athlete","sport":"Tennis","level":"College"},
  "summary_cards": {
    "weekly_load":"High","recovery_risk":"Medium",
    "next_event":"San Jose Open - Saturday","recent_results":"3 Wins / 2 Losses",
    "ai_focus":"Serve consistency + knee recovery"
  },
  "latest_agent_outputs": [
    {"agent_name":"Recovery Agent","severity":"medium",
     "summary":"Knee soreness appeared in 3 recent entries."}
  ]
}
```

`/dashboard/performance`
```json
{
  "win_loss":[{"date":"2026-06-01","result":"win"},{"date":"2026-06-05","result":"loss"}],
  "metrics":[{"metric_name":"serve_speed","data":[
    {"date":"2026-06-01","value":82},{"date":"2026-06-05","value":85}]}],
  "insights":[{"title":"Serve improving",
    "summary":"Serve speed increased across the last 3 sessions."}]
}
```

`/dashboard/sponsorship`
```json
{
  "opportunities":[{
    "brand_name":"Local Sports Recovery Clinic","category":"Recovery",
    "fit_score":0.82,
    "reason":"Matches the athlete's sport, location, and recovery-focused profile.",
    "status":"drafted","draft_email":"Hi..."
  }]
}
```

---

## 9. How this maps to the repo

```
TeamUP/
├── Backend/          # Dev 3 agent layer + (Dev 2 hooks)
│   ├── agents/
│   │   ├── orchestrator.py     # ASI:One entry point, conducts the loop
│   │   ├── librarian.py        # Parser: classify → entries
│   │   ├── recovery.py         # overtraining / wellness
│   │   ├── performance.py      # win/loss + skill trends
│   │   ├── sponsorship.py      # brand fit + draft email (approval-gated)
│   │   └── common/             # config, chat protocol, Claude, backend client
│   ├── mock_backend.py         # Dev 2 stand-in (full schema + dashboard routes)
│   ├── run_local.py / send_dump.py / asi_ping.py
│   └── readmes/                # Agentverse Overview READMEs (Innovation Lab badge)
└── Frontend/         # Dev 1 — Next.js dashboard
```

The agent layer reads/writes Dev 2's API; point `BACKEND_URL` at the real
service when up. `mock_backend.py` implements the same contract so the agents
run before Dev 2's service exists.

---

## 10. MVP build order

1. **Sentry first (hour 0).** `sentry_sdk.init()` in FastAPI + `npx @sentry/wizard` in Next.js before writing any other code. Captures real errors throughout the build.
2. **Database.** Create the tables; lock the schema before UI.
3. **Manual seed data.** ~10 training sessions, 5 match results, 5 recovery logs,
   3 calendar events, 2 sponsorship opportunities, 5 agent outputs — so the
   dashboard works before the full pipeline.
4. **Dashboard from DB only.** Frontend reads structured results; it never cares
   whether data came from photo, voice, text, or seed.
5. **Photo ingestion** → Claude vision → Parser → DB → dashboard.
6. **Voice ingestion** → Deepgram → Parser → DB → dashboard.
7. **Embed pipeline** → every `POST /entries` embeds text → RedisVL store →
   `embedded = true`. Lock this before RAG work starts.
8. **Agent outputs** → each specialist writes visible results to `agent_outputs`.
9. **Browserbase cache** → pre-scrape one tournament result + one opponent card.
   Live scraping is the happy path; these are the demo-day fallbacks.
10. **RAG + `/chat`** → RedisVL KNN retrieval → Claude generation → LangCache.
11. **Agent Memory** → add to Recovery agent once core pipeline is stable.
12. **Seed linguistic-drift entries** (12–14 fake entries) for Recovery demo.

**Hour-12 hard checkpoint:** input → sectioned entries → Recovery flag →
Performance trend → dashboard updates → chat answer, end-to-end. After that it's
polish.

---

## 11. Demo

```txt
1. Upload notebook photo  → history extracted → dashboard fills
2. Record a voice dump after a game (neutral — no mention of pain)
3. Agents update the dashboard: Performance trend, Logistics event, Sponsorship fit
4. Recovery Agent surfaces passive finding:
   "You haven't mentioned pain — but over 14 sessions your serve descriptions
    shifted from explosive to effortful. Consistent with early shoulder fatigue."
   [← THIS IS THE MOMENT]
5. Ask AI: "What should I focus on next week?"
   → RAG retrieves relevant entries → Claude answers with highlighted sources
6. Sponsorship Agent suggests a brand fit + drafts an email (approval-gated)
```

Positioning: *"A personal sports analytics OS for individual athletes. Upload
photos of old notebooks or record voice dumps after training, and our agent
system turns that unstructured history into a structured performance dashboard
with recovery insights, match trends, logistics, and sponsorship opportunities."*

**Submission checklist (track):** public ASI:One shared chat URL · Agentverse
profile URL(s) · public GitHub repo · 3–5 min demo video · problem + target-user
write-up.

---

## 12. Product rules

1. Build the database first.
2. Dashboard reads only from the database.
3. Agents write structured data into the database.
4. Inputs can be photo, voice, or text — all converge on the Parser.
5. Sponsorship is approval-based, never fully automatic.
6. Recovery is framed as wellness, not diagnosis.
7. The dashboard feels like sports analytics, not a note app.
8. Demo with seeded data before relying on full automation.
9. Landing page and heavy polish are last.
10. The story: messy logs become structured athletic intelligence.

**Never let the demo depend on:** ASI:One marketplace routing being on the
critical path (it's the entry point but the Orchestrator runs deterministically),
live scraping with no cached fallback, or any auto-send outreach.

**Browserbase fallback rule:** always have a pre-scraped tournament result and
opponent card cached before demo day. Live scraping is the happy path, not the
demo dependency.

**Sentry rule:** initialise at hour 0, use it to communicate bugs during the
build, document one real catch in the submission write-up, show the dashboard
for 30 seconds in the demo video.
