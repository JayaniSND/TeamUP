-- BASELINE — Supabase schema
-- Matches exactly what Backend/main.py reads and writes.
--
-- HOW TO RUN:
--   Supabase dashboard → SQL Editor → New query → paste this whole file → Run.
--   Then populate demo data:
--     curl -X POST "http://127.0.0.1:8000/admin/seed?user_id=a0000000-0000-0000-0000-000000000001"
--
-- Notes:
--   • user_id is TEXT (not a FK) so both UUIDs and ids like 'demo-athlete' work,
--     and inserts never fail on a missing users row — fine for the hackathon.
--   • RLS is disabled so the anon/publishable key can read+write (matches the
--     already-working `entries` table). Do NOT ship this to production as-is.
--   • `create table if not exists` is safe to re-run and won't touch existing tables.

-- ── raw_inputs ─────────────────────────────────────────────────────
create table if not exists public.raw_inputs (
    id          uuid primary key default gen_random_uuid(),
    user_id     text,
    input_type  text,                         -- photo | voice | text
    raw_text    text,
    file_url    text,
    created_at  timestamptz default now()
);

-- ── entries (core flexible table; Parser writes here first) ────────
create table if not exists public.entries (
    id            uuid primary key default gen_random_uuid(),
    user_id       text,
    raw_input_id  uuid,
    section       text,
    title         text,
    text          text,
    tags          text[],
    confidence    double precision,
    metadata      jsonb default '{}'::jsonb,
    embedded      boolean default false,
    created_at    timestamptz default now()
);

-- ── training_sessions ──────────────────────────────────────────────
create table if not exists public.training_sessions (
    id                uuid primary key default gen_random_uuid(),
    user_id           text,
    date              date,
    sport             text,
    session_type      text,
    duration_minutes  integer,
    intensity         integer,
    focus_area        text,
    notes             text,
    created_at        timestamptz default now()
);

-- ── match_results ──────────────────────────────────────────────────
create table if not exists public.match_results (
    id          uuid primary key default gen_random_uuid(),
    user_id     text,
    date        date,
    opponent    text,
    event_name  text,
    result      text,                         -- win | loss | draw
    score       text,
    key_stats   jsonb default '{}'::jsonb,
    notes       text,
    created_at  timestamptz default now()
);

-- ── recovery_logs ──────────────────────────────────────────────────
create table if not exists public.recovery_logs (
    id              uuid primary key default gen_random_uuid(),
    user_id         text,
    date            date,
    soreness_level  integer,
    fatigue_level   integer,
    sleep_hours     double precision,
    injury_area     text,
    pain_level      integer,
    risk_level      text,
    notes           text,
    created_at      timestamptz default now()
);

-- ── metrics ────────────────────────────────────────────────────────
create table if not exists public.metrics (
    id               uuid primary key default gen_random_uuid(),
    user_id          text,
    metric_name      text,
    metric_value     double precision,
    unit             text,
    date             date,
    source_entry_id  uuid,
    created_at       timestamptz default now()
);

-- ── calendar_events ────────────────────────────────────────────────
create table if not exists public.calendar_events (
    id          uuid primary key default gen_random_uuid(),
    user_id     text,
    title       text,
    event_type  text,                         -- game | tournament | training | travel | recovery
    start_time  text,
    end_time    text,
    location    text,
    source      text,
    metadata    jsonb default '{}'::jsonb,
    created_at  timestamptz default now()
);

-- ── sponsorship_opportunities ──────────────────────────────────────
create table if not exists public.sponsorship_opportunities (
    id             uuid primary key default gen_random_uuid(),
    user_id        text,
    brand_name     text,
    category       text,
    contact_email  text,
    fit_score      double precision default 0,
    reason         text,
    status         text default 'suggested',  -- suggested | drafted | sent | replied | rejected
    draft_email    text,
    created_at     timestamptz default now()
);

-- ── agent_outputs (dashboard insight cards) ────────────────────────
create table if not exists public.agent_outputs (
    id                  uuid primary key default gen_random_uuid(),
    user_id             text,
    agent_name          text,
    section             text,
    summary             text,
    severity            text default 'info',
    recommended_action  text default '',
    related_entry_ids   jsonb default '[]'::jsonb,
    created_at          timestamptz default now()
);

-- ── athlete_profiles (optional — real profile instead of placeholder) ──
create table if not exists public.athlete_profiles (
    user_id         text primary key,
    name            text,
    sport           text,
    position        text,
    level           text,
    location        text,
    dominant_side   text,
    goals           jsonb default '[]'::jsonb,
    strengths       jsonb default '[]'::jsonb,
    weaknesses      jsonb default '[]'::jsonb,
    injury_history  jsonb default '[]'::jsonb,
    created_at      timestamptz default now()
);

-- ── allow the anon/publishable key to read + write (hackathon) ─────
alter table public.athlete_profiles          disable row level security;
alter table public.raw_inputs                disable row level security;
alter table public.entries                   disable row level security;
alter table public.training_sessions         disable row level security;
alter table public.match_results             disable row level security;
alter table public.recovery_logs             disable row level security;
alter table public.metrics                   disable row level security;
alter table public.calendar_events           disable row level security;
alter table public.sponsorship_opportunities disable row level security;
alter table public.agent_outputs             disable row level security;

-- Helpful indexes for the per-user dashboard queries.
create index if not exists idx_entries_user        on public.entries (user_id, created_at desc);
create index if not exists idx_match_results_user   on public.match_results (user_id, date desc);
create index if not exists idx_metrics_user         on public.metrics (user_id, date desc);
create index if not exists idx_training_user        on public.training_sessions (user_id, date desc);
create index if not exists idx_recovery_user        on public.recovery_logs (user_id, date desc);
create index if not exists idx_agent_outputs_user   on public.agent_outputs (user_id, created_at desc);
create index if not exists idx_calendar_user        on public.calendar_events (user_id);
create index if not exists idx_sponsorship_user     on public.sponsorship_opportunities (user_id);
