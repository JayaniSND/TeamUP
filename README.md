# SportsMom 

SportsMom: Multi-Agent Sports Analytics OS

tag:innovationlab tag:hackathon

    CalHacks AI 2026, SportsMom (codename BASELINE)

SportsMom is a network of specialist uAgents that acts as the support team a self-managed individual-sport athlete (tennis first) doesn't have. The athlete dumps a voice note, a photo of a handwritten notebook page, or typed text, and the agent network transcribes it, classifies it, files it, and turns it into overtraining flags, performance trends, opponent scouting reports, sponsorship drafts, and fully researched tournament trips, all reachable through a single ASI:One chat session, with a React dashboard on top for the days you'd rather look than talk.

    Raw input (voice / photo / text) is normalized to plain text.
    The Librarian classifies and files it into structured journal entries.
    The Orchestrator routes intent to the right specialist agent(s).
    Specialists (Recovery, Performance, Scout, Sponsorship, Logistics) reason over the athlete's data and return insights or drafts.
    Outcomes land in Supabase and surface through the dashboard, ASI:One replies, and (for Logistics) a real Stripe-gated tournament-entry flow.

Agent roles and responsibilities
1) Orchestrator Agent

    The single ASI:One / Agentverse entry point for the whole system.
    Classifies every incoming message into one of three intents: log, ask, or action.
    log → Librarian → fan-out to specialists → correlates results into one reply.
    ask → routes to the POST /chat RAG endpoint and relays the grounded answer.
    action → routes straight to the named specialist (Recovery / Performance / Sponsorship / Logistics / Scout).
    Falls back to inline Claude calls when no worker addresses are configured, so a demo never goes dark.

2) Librarian Agent

    The front door for every raw dump.
    Uses Claude Haiku 4.5 to split a dump into entries across nine sections: training, performance, match_results, recovery, coaching, logistics, sponsorship, goals, media_notes.
    Writes each entry to Supabase via POST /entries and notifies whichever specialists care about what just got filed.
    Runs in two modes: standalone (replies directly over ASI:One) and orchestrator-driven (returns a classify_result envelope).

3) Recovery Agent

    Pulls the last 60 journal entries plus 14 days of recovery logs, training sessions, and metrics.
    Asks Claude Sonnet 4.6 for a risk level (none / low / medium / high), affected body parts, a recommended action, and a behavioral pattern summary (e.g. a burnout arc).
    Suggests which agent to open next, surfaced as text rather than auto-dispatched.
    A 72-hour deduplication guard prevents duplicate alerts from the same passive sweep.

4) Performance Agent

    Reads the last 10 matches plus recent training sessions and 20 recent metrics.
    Returns a trend (improving / stable / declining), the athlete's strongest and weakest area, and a recommended focus.
    Triggers automatically whenever a match result, training log, or performance entry is filed.
    Output lands in the same agent_outputs table the dashboard reads from.

5) Scout Agent

    Takes a match log or an opponent's name and sends Browserbase + Stagehand out to research them on the open web.
    Has Claude synthesize the research into patterns, strengths, weaknesses, and a tactical recommendation.
    Files the report as both a coaching journal entry and an agent_outputs card.
    Triggers automatically whenever a match result comes in.

6) Sponsorship Agent

    Reads the athlete's profile, recent matches, metrics, and media notes.
    Has Claude pick a brand fit and score it, then drafts a cold outreach email.
    Status always stays "drafted"; nothing sends itself. The frontend's draft → approve → send flow is the only path an email can actually leave through.

7) Logistics Agent

    Runs as a 3-stage interactive conversation rather than a single request/reply.
    Search: parallel fan-out to an external Flights agent and an external Hotels agent on the open Agentverse marketplace, plus a live ITF W15/W25 tournament scrape via Browserbase; resolved dates create a Google Calendar event.
    Pick: the athlete replies with a number to choose a tournament (10-minute window).
    Payment gate (optional): a Stripe TEST mode Checkout Session ($5.00 fee); on confirmation shows the ITF entry review screen, but never auto-submits the actual entry.

Protocols and standards used

    Fetch.ai Agent Chat Protocol: implemented by all seven agents, which is what makes the whole workflow usable directly from an ASI:One conversation with no custom frontend required.
    Fetch.ai Agentverse: every agent runs as a mailbox agent, registered and reachable by a stable handle/address through the Almanac.
    ASI:One: the user-facing conversational entry point and bonus-track router.
    Fetch.ai Payment Protocol: implemented via the Logistics agent's Stripe Checkout step.
    Agent-to-agent orchestration: Logistics collaborates with two independently operated Flights/Hotels agents purely through natural language, across organizational boundaries.
    Anthropic Claude: Haiku 4.5 for high-volume classification, Sonnet 4.6 for synthesis/reasoning (Recovery, Performance, Scout, Sponsorship, Logistics), and Claude vision for notebook-photo OCR.
    Deepgram nova-3: pre-recorded REST transcription and live streaming mic transcription.
    Browserbase + Stagehand: natural-language browser automation for ITF tournament search and opponent research, no hardcoded selectors.
    Redis (RedisVL + LangCache): KNN vector retrieval and semantic answer caching behind the RAG chat endpoint.
    Supabase (Postgres): the database every table (entries, matches, recovery_logs, metrics, agent_outputs, sponsorship_opportunities, calendar_events) writes to.
    Sentry (optional): error monitoring and performance tracing, initialized only if SENTRY_DSN is set.

High-level workflow

    Athlete sends a voice note, notebook photo, or typed text.
    Voice → POST /convert/voice (Deepgram nova-3); Photo → POST /convert/photo (Claude vision); Text needs no conversion.
    POST /ingest runs the full pipeline: transcribe/OCR → classify (Librarian) → embed → store (Supabase).
    Orchestrator classifies intent and routes to the Librarian, the RAG chat endpoint, or a named specialist.
    Specialist agents read from Supabase, reason with Claude, and write results to agent_outputs (or sponsorship_opportunities / calendar_events for Sponsorship and Logistics).
    Frontend dashboard and ASI:One replies both read the same underlying data, so the chat-only flow and the dashboard flow always stay in sync.
    For Logistics, a confirmed tournament pick can optionally pass through a real Stripe test-mode payment gate before showing (never submitting) the ITF entry review.

Project structure

TeamUP/
├── AGENTS.md                 # Frontend design system spec ("Aurora Glass")
├── Backend/
│   ├── agents/
│   │   ├── orchestrator.py   # Intent router and conductor
│   │   ├── librarian.py      # Classification and filing
│   │   ├── recovery.py       # Overtraining / wellness detection
│   │   ├── performance.py    # Trend analysis
│   │   ├── scout.py          # Opponent research
│   │   ├── sponsorship.py    # Brand matching + email drafting
│   │   └── logistics.py      # Travel, tournaments, calendar, payment
│   ├── common/                # Shared chat/config/backend-client helpers
│   ├── integrations/          # Browserbase/Stagehand, Stripe, Google Calendar, Deepgram
│   ├── processing/            # voicetotext.py, phototext.py: input normalization
│   ├── readmes/                # Agentverse Overview READMEs, one per agent
│   ├── authorize_gcal/         # Google Calendar OAuth flow
│   ├── calandar_client.py
│   ├── config.py
│   ├── database.py
│   ├── main.py                 # FastAPI backend (Supabase-backed)
│   ├── mock_backend.py         # Local mock backend for offline/seeded demos
│   ├── rag.py                  # RAG / chat pipeline (Redis + Claude)
│   ├── run_local.py            # One-command Bureau run of all agents locally
│   ├── send_dump.py            # Test client: sends a raw dump to a deployed agent
│   ├── asi_ping.py             # ASI:One connectivity probe
│   └── requirements.txt
├── Frontend/                  # React 18 + TS + Vite + Tailwind v4 dashboard ("Aurora Glass")
├── requirements.txt
└── README.md

Quick start
1) Install dependencies

python3 -m venv Backend/venv
source Backend/venv/bin/activate
pip install -r Backend/requirements.txt

cd Frontend
npm install
cd ..

2) Configure environment

cp Backend/.env.example Backend/.env

At minimum:

    ANTHROPIC_API_KEY: Claude classification, synthesis, and vision OCR
    AGENTVERSE_KEY: mailbox registration for all seven agents
    DEEPGRAM_API_KEY: voice transcription (REST + live mic)
    SUPABASE_URL / SUPABASE_KEY: persistence layer

Optional, depending on which flows you want live rather than gracefully skipped:

    ASI_ONE_API_KEY: ASI:One bonus router
    BROWSERBASE_API_KEY / BROWSERBASE_PROJECT_ID: Scout + Logistics browser automation
    STRIPE_SECRET_KEY: real test-mode Checkout gate (omit to skip the payment gate entirely)
    GOOGLE_CALENDAR credentials: via Backend/authorize_gcal
    SENTRY_DSN: backend error monitoring
    LIBRARIAN_ADDRESS / RECOVERY_ADDRESS / LOGISTICS_ADDRESS: filled in after first boot, so the Orchestrator can route to already-running agents instead of falling back to inline Claude calls

3) Start backend, agents, and frontend

# Backend (FastAPI data layer)
cd Backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000

# Agents: all seven in one local Bureau (new terminal)
cd Backend
source venv/bin/activate
python run_local.py

# Frontend (new terminal)
cd Frontend
npm run dev

Frontend: http://localhost:5173

Backend/API: http://localhost:8000

Agent ports (local Bureau): Librarian 8001 · Recovery 8002 · Orchestrator 8003 (others assigned per Backend/config.py)
Useful endpoints

    POST /convert/photo: notebook image to OCR text
    POST /convert/voice: audio to transcript
    POST /ingest: full pipeline, transcribe/OCR to classify to embed to store
    POST /entries / GET /entries: journal entry CRUD
    GET /metrics, /match_results, /training_sessions, /recovery_logs: read tables
    POST /agent_outputs / GET /agent_outputs: specialist insight cards
    POST /sponsorship_opportunities: sponsorship draft storage
    POST /calendar/add: calendar event storage
    GET /dashboard/*: pre-shaped dashboard reads (overview, performance, recovery, matches, training, logistics, sponsorship)
    POST /chat: RAG question answering, grounded in the athlete's own data
    POST /admin/seed / /admin/clear / /admin/backfill: demo data management

Submission details

    Public ASI:One shared chat session URL showing the complete workflow:
    [ ]

    Agentverse Agent Profile URL(s) for each submitted agent:
        Orchestrator: [ ]
        Librarian: [ ]
        Recovery: [ ]
        Performance: [ ]
        Scout: [ ]
        Sponsorship: [ ]
        Logistics: [ ]

    Public GitHub repository URL:
    [ ]

    Short demo video:
    [ ]

    Brief description of the problem, target user, and outcome produced by the agent:
    [ ]

Agentverse submission checklist

    Add this repo link + public URL in the CalHacks AI submission fields.
    Keep each agent's Agentverse Overview README (Backend/readmes/) written as plain-English capability copy: what it does, example queries, sample responses, since that's what ASI:One's agent search actually uses, not technical documentation.
    Confirm every agent (not just the Orchestrator) has mailbox=True and includes the chat protocol with publish_manifest=True.
    For a full demo submission, include a live code link, a 3–5 minute demo video, and any required API keys or setup notes for judges (non-secret placeholders only).
    Treat the no-custom-frontend ASI:One flow as a hard demo requirement: the full dump → classify → route → specialist → reply loop should work end to end from a single ASI:One chat session, independent of the dashboard.

Deployment notes

    Backend/run_local.py spins up all seven agents in a single local Bureau for offline/dev demos; deployed agents instead register individually as mailbox agents on Agentverse.
    Browser real-time updates come from dashboard polling against the FastAPI endpoints above; ASI:One updates arrive as chat replies from the Orchestrator.
    Supabase is the system of record for entries, matches, recovery logs, metrics, agent outputs, sponsorship opportunities, and calendar events.
    Redis (RedisVL + LangCache) sits in front of the RAG chat endpoint; if Redis is unreachable, retrieval falls back to a recency query instead of failing.
    The Stripe payment gate and Browserbase automation degrade gracefully: without STRIPE_SECRET_KEY the payment step is simply skipped, and without Browserbase credentials Scout/Logistics fall back to whatever data is already in Supabase.
    Sentry is optional and only initializes if SENTRY_DSN is set.

License

MIT
