# Athlete Analytics OS — Frontend Dashboard

> The athlete dashboard that builds itself from your notebooks and voice logs.

This file is the **source of truth** for the frontend design system and build plan. It was
researched and refined before any code was written (see _Design Research_ below), then used to
build the dashboard in `Frontend/`.

---

## Product context (from `framework_draft.md`)

A personal sports-analytics OS for **self-managed individual-sport athletes** (tennis first).
The athlete brain-dumps after practice or a match — voice, text, or a photo of their paper
notebook — and an agent network underneath transcribes it, files each piece into the right
section, surfaces progress graphs, answers questions about their own history, flags
overtraining, finds their next tournament, and drops it on their calendar.

The **journal is the face; the autonomous agent layer is the engine.** The dashboard's job is to
make that agent layer _legible_ — every panel reflects what an agent (Librarian, Recovery,
Logistics, Scout) produced from raw athlete input.

**Backend sections (single source of truth, mirror in the frontend types):**
`performance · injury_log · coaching · energy_nutrition · logistics · training`
**Metrics seen so far:** `training_volume_mi`, `recovery_score`.
Demo athlete = tennis player with a recurring **right-knee soreness / overtraining** pattern.

---

## Aurora Glass Dashboard Design System

This is the current frontend visual source of truth. Future frontend work must follow the
**Aurora Glass Dashboard** style in its approved white / green direction. Do not revert to the
old dark blue / purple futuristic direction, and do not flatten it into a generic plain SaaS UI.

**Visual style direction:** clean, premium, calm glassmorphism-inspired dashboard with Apple-like
softness and a compact SaaS command-center layout. The UI should feel like one polished product
window floating over a white, soft off-white, or very pale green background.

**Color palette:** white, off-white, and very pale green backgrounds; mint, sage, emerald, and
teal-green accents; dark charcoal or deep green-gray primary text; muted gray-green secondary
text; soft green-tinted borders; and semantic status colors tuned for a light glass interface:
green positive, soft amber warning, muted rose negative only where needed, teal neutral, and
sage/emerald AI.

**Typography rules:** use Inter/system sans. Keep labels small, uppercase, and widely tracked.
Use medium/semi-bold weights rather than heavy bold. Metric values use `tabular-nums`, large type,
and high-contrast dark text or emerald/teal accent colors.

**Layout rules:** the app shell is a centered rounded glass container with an internal left
sidebar divider, compact top toolbar, bento dashboard grid, and optional right AI rail. Desktop
should feel information-rich without becoming crowded; tablet and mobile stack cards cleanly.

**Glassmorphism rules:** major surfaces use translucent white or green-tinted glass, soft blur on
large shell/card surfaces, 1px light green-tinted borders, inner highlight lines, soft shadows, and
subtle mint/emerald glow. Keep the interface slightly glassy and premium. Avoid dark purple/blue
glass as the main theme, avoid harsh neon green, and avoid plain flat white cards. Avoid heavy blur
on tiny repeated children to keep hover/selection smooth.

**Component rules:** sidebar nav uses rounded glass pills with a soft green active state and
subtle glow. Header inputs/actions are frosted pills. Cards, chart containers, lists, chat bubbles,
badges, and buttons must share the same white/green glass language. Charts use light green-gray
grids with emerald/sage/teal series. Tables/lists use compact glass rows and subtle pale-green
hover states, not default table styling.

**Animation rules:** transitions are subtle, 180-250ms, and limited to transform, opacity,
background, border, and color. Use CSS transitions/keyframes instead of JS-driven hover animation.
No gratuitous motion.

**Performance rules:** keep cursor hover/select interactions instant. Do not animate large
box-shadows or blur filters. Memoize expensive React cards/charts where useful. Keep mock data
module-level and prop identities stable. Prefer CSS-only hover lift and one-shot mount fades.

---

## Reference Alignment

The approved dashboard direction is now the white / green **Aurora Glass Dashboard**. The previous
blue / purple / pink dark-glass direction is retired. Future work must preserve the current clean,
premium, calm glassmorphism language and only simplify density when needed.

Required direction:

- Keep the glassmorphism dashboard style.
- Use white, soft off-white, and very pale green backgrounds.
- Use mint, sage, emerald, and teal-green accents.
- Keep translucent or softly frosted cards, rounded panels, subtle glow, and soft blur on large surfaces.
- Keep dark charcoal or deep green-gray text for readability.
- Use soft green-tinted borders, light dividers, and subtle shadows.
- Keep rounded panels, compact controls, and clean green highlights.
- Do **not** revert to a plain flat SaaS UI.
- Do **not** revert to the dark futuristic purple/blue theme.
- Avoid purple/blue as the main theme.
- Do **not** redesign into a completely different style.
- Keep the dashboard compact, aligned, laptop-focused, and easy to scan.
- Preserve AI chat usability, internal scrolling, and alignment.
- Only simplify, compact, and prioritize the existing dashboard; do not add unnecessary data sections.

The dashboard should be read as a density and composition guide: one polished product window,
compact sidebar/header, a small set of high-impact KPI cards, one main chart, one compact
secondary visual/status area, a useful alert/action summary, and a fully usable AI chat rail.

---

## Tech stack & tooling decision

- **React 18 + TypeScript + Vite** — there is no existing React app and no SSR need; Vite is the
  fastest path to a self-contained, mock-data dashboard. (The `framework_draft.md` mentions
  Next.js, but App Router buys us nothing here; the suggested `app/dashboard/page.tsx` structure
  is adapted to a Vite `src/` layout.)
- **Tailwind CSS v4** (`@tailwindcss/vite`, CSS-first config with design tokens as CSS variables).
- **shadcn/ui-style components, hand-built** — no CLI/registry dependency. A `cn()` helper
  (`clsx` + `tailwind-merge`) plus small primitives in `components/ui/`.
- **Recharts** for charts, **lucide-react** for icons, **framer-motion** for _subtle_ transitions
  only (fade/slide on mount, panel hover). No gratuitous animation.

---

## Design system

**Aesthetic:** white / off-white / very pale green canvas with one rounded translucent app shell.
Cards are softly frosted white/green glass panels with light green-tinted borders, inner highlight
lines, subtle mint glow, and soft blur only on larger surfaces. The dashboard should feel clean,
premium, calm, compact, modern, slightly glassy, and readable at a glance.

**Color tokens** (defined as CSS vars in `src/index.css`, consumed via Tailwind):

| Token | Value | Use |
|---|---|---|
| `--bg` | `#F6FBF7` | white / pale green page base |
| `--surface` | `rgba(255,255,255,0.56)` | translucent white glass card base |
| `--surface-2` | `rgba(226,246,236,0.58)` | frosted nested rows / chips |
| `--surface-3` | `rgba(212,238,225,0.38)` | low-emphasis green-tinted glass fills |
| `--line` | `rgba(69,133,105,0.18)` | light green-gray dividers |
| `--text` | `#17332B` | key numbers, headings, labels |
| `--text-muted` | `rgba(36,65,56,0.76)` | secondary labels |
| `--text-dim` | `rgba(64,92,82,0.54)` | tertiary meta |
| `--accent` | `#1F9F68` | primary emerald action/accent |
| `--positive` | `#25B97D` | recovery good, wins |
| `--warning` | `#B9861E` | risk, caution |
| `--negative` | `#C85F76` | losses, high risk |
| `--ai` | `#4E9A7F` | AI / agent surfaces |

**Elevation:** `.glass-card` is a light frosted surface with translucent white/green tint. Depth
comes from low-opacity green glow shadows, light green borders, and inner white highlights. Avoid
animating blur or large shadows on hover.

**Gradients:** use white, mint, sage, emerald, and teal gradients sparingly to support hierarchy
inside the existing glass language. Avoid purple/blue as the main theme and avoid harsh lime or
oversaturated neon green.

**Status semantics:** green = good/low-risk/win, amber = medium/caution, muted rose = high-risk/loss,
teal/sage = neutral/performance, emerald/sage = agent/AI. Every metric carries a status that drives
its accent.

**Typography:** Inter/system sans. Labels are small uppercase tracked text. Values use
`tabular-nums`, medium/semi-bold weights, and high-contrast dark text or emerald/teal accents.

---

## Layout

Desktop-first **compact bento grid**: `Sidebar | Main one-screen dashboard | optional AI panel`.
The primary dashboard must fit without vertical scrolling in standard laptop frames:
`1440x900` and `1366x768`.

```
┌──────┬───────────────────────────────────────┬──────────────┐
│      │  DashboardHeader (athlete, actions)    │              │
│ Side │  KPI cards (3 high-impact metrics)     │  AIChatPanel │
│ bar  │  Main performance chart                │  (optional   │
│      │  Compact form/recovery status          │   right rail)│
│      │  Compact alerts / next action summary  │              │
└──────┴───────────────────────────────────────┴──────────────┘
```

Density rules:

- Keep only high-volume and high-impact dashboard data.
- Use 3 KPI cards by default; do not add low-priority stat cards.
- Use one main chart and one compact secondary chart/status block.
- Replace long lists with small summaries, badges, and mini indicators.
- If a table/list appears, show only the top 3-5 most important rows.
- Keep the sidebar/header compact.
- Do not turn the dashboard into a long report page.

Responsive: desktop = compact bento; tablet/mobile may stack, but the desktop target is a
single laptop viewport with no vertical scroll.

---

## Component strategy

Reusable primitives drive everything. Panels share one `SectionCard` shell so every section has
the same header + AI action affordance. The primary dashboard should render only the sections
needed for one-glance understanding; lower-priority modules can remain in code but should not
crowd the default laptop view.

- `SectionCard` — glass shell: title, icon, optional subtitle, **section-level AI action button**
  (slot), children. Every section is a `SectionCard`.
- `MetricCard` — icon + uppercase label + big tabular value + trend/status line + status accent.
- `AgentInsightCard` — sage/emerald-tinted callout: which agent produced it + insight + suggested
  adjustment. Used in Recovery and AI surfaces to make the agent layer legible.
- `ui/` primitives: `Button`, `Badge`, `cn()` util.

**Section → AI action mapping** (each section gets exactly one contextual action):

| Section | AI action |
|---|---|
| Overview | Ask AI |
| Performance | Explain trend |
| Training | Generate plan |
| Match Results | Ask AI (per match) |
| Recovery | Suggest adjustment |
| Schedule | Add to calendar |
| Sponsorship | Draft email |

---

## File structure (Vite-adapted)

```
Frontend/
  index.html
  package.json · vite.config.ts · tsconfig*.json
  src/
    main.tsx
    App.tsx                      # dashboard page (was app/dashboard/page.tsx)
    index.css                    # tokens + tailwind + glass utilities
    components/
      dashboard/
        Sidebar.tsx  DashboardHeader.tsx  OverviewCards.tsx
        PerformanceChart.tsx  TrainingPanel.tsx  MatchResultsPanel.tsx
        RecoveryPanel.tsx  SchedulePanel.tsx  SponsorshipPanel.tsx
        AIChatPanel.tsx  AgentInsightCard.tsx  MetricCard.tsx  SectionCard.tsx
      ui/  (Button.tsx  Badge.tsx)
    data/    mockAthleteData.ts   # ALL mock data isolated here, API-shaped
    types/   athlete.ts           # mirrors backend sections/metrics
    lib/     utils.ts             # cn()
```

---

## Implementation plan

1. Scaffold Vite + React-TS, install deps, wire Tailwind v4 + tokens in `index.css`.
2. `types/athlete.ts` mirroring backend sections/metrics; `lib/utils.ts` (`cn`).
3. `mockAthleteData.ts` — realistic tennis athlete (Maya Chen), API-shaped so it can later be
   swapped for `/entries`, `/metrics`, `/progress`, `/chat` calls. Encode the knee-soreness
   overtraining storyline so Recovery + AI feel real.
4. `ui/` primitives + `cn`.
5. Reusable cards: `SectionCard`, `MetricCard`, `AgentInsightCard`.
6. Layout shell: `Sidebar`, `DashboardHeader`, bento grid in `App.tsx`.
7. Section panels (Overview, Performance chart, Training, Match, Recovery, Schedule, Sponsorship).
8. `AIChatPanel` (right rail / toggle) with section-connected suggested prompts + canned replies.
9. Responsive pass + subtle framer-motion mount transitions.
10. `npm run build` to typecheck/verify; report file paths.

## Product rules (enforced in UI)

1. Mock data only, isolated in `data/mockAthleteData.ts`, API-shaped (DB-ready later).
2. Recovery = wellness / self-management language only — **no medical diagnosis** wording.
   Use "recovery signal", "risk pattern", "suggested adjustment", "wellness insight".
3. Sponsorship: **Find → Draft email → user approves → Send**. Never auto-send; button drafts only.
4. This is an analytics command center, not a journal/notebook UI.
5. Reusable components, minimal animation, looks real with no backend.
```
