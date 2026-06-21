import type { AthleteData } from "@/types/athlete";

/**
 * Realistic mock data for a single tennis athlete.
 *
 * Isolated here so it can be replaced 1:1 by API calls later (see types in
 * `types/athlete.ts`). The storyline is deliberately coherent with the backend
 * seed in `Backend/mock_backend.py`: recurring RIGHT-KNEE soreness + a training
 * volume spike → the Recovery agent flags an overtraining risk pattern, and the
 * dashboard surfaces it. Tennis player, mid-season, San Jose Open coming up.
 *
 * NOTE: this is a module-level constant on purpose — it is created once, never
 * re-derived on render, so memoized panels never see new prop identities.
 */
export const athleteData: AthleteData = {
  profile: {
    name: "Maya Chen",
    sport: "Tennis · Singles",
    level: "ITF Pro · Open Division",
    handle: "@mayachen",
    currentWeek: "Week 24 · 2026 Season",
    avatarInitials: "MC",
    worldRank: 184,
  },

  goal: {
    title: "Break into the Top 150",
    target: "Top 150",
    progressPct: 62,
    detail: "World #184 → #150 by season end",
  },

  intake: {
    capturedAt: "2h ago",
    sources: ["voice", "notebook"],
    summary:
      "“Knee a little sore after serve practice — hit ~80 min, won the tune-up set 6-4, felt sharp on returns.”",
    agent: "Librarian",
    filed: [
      { label: "Training · +1 session", status: "neutral" },
      { label: "Recovery · knee soreness", status: "warning" },
      { label: "Match · result logged", status: "positive" },
    ],
  },

  // Trimmed to the three numbers that matter most at a glance — big, simple.
  overview: [
    {
      id: "winrate",
      label: "Win Rate",
      value: "63%",
      detail: "5W · 3L · last 8",
      status: "positive",
      icon: "Trophy",
    },
    {
      id: "recovery",
      label: "Recovery",
      value: "55",
      detail: "Medium risk · right knee",
      status: "warning",
      icon: "HeartPulse",
    },
    {
      id: "event",
      label: "Next Match",
      value: "12 days",
      detail: "San Jose Open · Hard court",
      status: "neutral",
      icon: "CalendarDays",
    },
  ],

  performance: [
    { date: "Mon", trainingLoad: 52, recoveryScore: 78, matchPerformance: null },
    { date: "Tue", trainingLoad: 64, recoveryScore: 74, matchPerformance: 71 },
    { date: "Wed", trainingLoad: 48, recoveryScore: 72, matchPerformance: null },
    { date: "Thu", trainingLoad: 76, recoveryScore: 64, matchPerformance: 58 },
    { date: "Fri", trainingLoad: 70, recoveryScore: 61, matchPerformance: null },
    { date: "Sat", trainingLoad: 88, recoveryScore: 55, matchPerformance: 82 },
    { date: "Sun", trainingLoad: 60, recoveryScore: 59, matchPerformance: null },
  ],

  training: {
    sessions: [
      {
        id: "s1",
        date: "Sat · Jun 13",
        focus: "Serve consistency + court footwork",
        durationMin: 95,
        intensity: "Peak",
        section: "training",
      },
      {
        id: "s2",
        date: "Thu · Jun 11",
        focus: "Long baseline rally session",
        durationMin: 80,
        intensity: "High",
        section: "training",
      },
      {
        id: "s3",
        date: "Wed · Jun 10",
        focus: "Footwork drills + light hitting",
        durationMin: 60,
        intensity: "Moderate",
        section: "training",
      },
      {
        id: "s4",
        date: "Mon · Jun 8",
        focus: "Hill repeats + conditioning",
        durationMin: 55,
        intensity: "High",
        section: "training",
      },
    ],
    weeklyTotalMin: 290,
    suggestedFocus:
      "Cap total load this week and protect the right knee — shift one high-intensity block to technical serve work.",
  },

  matches: [
    {
      id: "m1",
      date: "Jun 13",
      opponent: "R. Alvarez",
      result: "W",
      score: "6-4, 7-5",
      note: "Serve held up under pressure. Closed out tight second set.",
    },
    {
      id: "m2",
      date: "Jun 7",
      opponent: "K. Novak",
      result: "L",
      score: "3-6, 6-4, 4-6",
      note: "Faded physically in the third — knee tightened up late.",
    },
    {
      id: "m3",
      date: "Jun 1",
      opponent: "S. Whitman",
      result: "W",
      score: "6-2, 6-3",
      note: "Dominant from the baseline, high first-serve percentage.",
    },
    {
      id: "m4",
      date: "May 26",
      opponent: "L. Park",
      result: "W",
      score: "7-6, 6-4",
      note: "Clutch tiebreak. Movement was sharp all match.",
    },
    {
      id: "m5",
      date: "May 20",
      opponent: "D. Ferreira",
      result: "L",
      score: "4-6, 5-7",
      note: "Second-serve return cost points on key games.",
    },
  ],

  // Recent matches for the win/loss form graph (oldest → newest).
  form: [
    { id: "f1", label: "May 12", opponent: "M. Sato", result: "W", score: "6-3, 6-4", value: 73 },
    { id: "f2", label: "May 16", opponent: "P. Adler", result: "L", score: "5-7, 4-6", value: 48 },
    { id: "f3", label: "May 20", opponent: "D. Ferreira", result: "L", score: "4-6, 5-7", value: 45 },
    { id: "f4", label: "May 26", opponent: "L. Park", result: "W", score: "7-6, 6-4", value: 71 },
    { id: "f5", label: "Jun 1", opponent: "S. Whitman", result: "W", score: "6-2, 6-3", value: 82 },
    { id: "f6", label: "Jun 7", opponent: "K. Novak", result: "L", score: "3-6, 6-4, 4-6", value: 51 },
    { id: "f7", label: "Jun 10", opponent: "J. Reyes", result: "W", score: "6-3, 7-5", value: 77 },
    { id: "f8", label: "Jun 13", opponent: "R. Alvarez", result: "W", score: "6-4, 7-5", value: 84 },
  ],

  recovery: {
    risk: "warning",
    riskLabel: "Medium",
    sorenessTrend: [
      { day: "Jun 8", value: 35 },
      { day: "Jun 10", value: 48 },
      { day: "Jun 11", value: 52 },
      { day: "Jun 13", value: 64 },
    ],
    fatigueLevel: 62,
    sleepHours: 6.8,
    focusArea: "Right knee",
  },

  // The weekly calendar is the dashboard centerpiece. This is the lighter,
  // recovery-aware week the agents recommended (knee soreness storyline), with
  // a look-ahead to the San Jose Open prep. Today = Sat Jun 20.
  weeklyCalendar: {
    rangeLabel: "Jun 15 – Jun 21 · This week",
    upcomingLabel: "Next week",
    upcoming: [
      "Mon 22 · Serve clinic",
      "Wed 24 · Tune-up exhibition",
      "Jun 30 · Travel → San Jose",
      "Jul 2 · San Jose Open R1",
    ],
    days: [
      {
        day: "Mon",
        date: 15,
        slots: [{ id: "w1", title: "Technical serve", time: "9:00 AM", kind: "training" }],
      },
      {
        day: "Tue",
        date: 16,
        slots: [
          { id: "w2", title: "Baseline rally", time: "10:00 AM", kind: "training" },
          { id: "w3", title: "Footwork drills", time: "4:00 PM", kind: "training" },
        ],
      },
      {
        day: "Wed",
        date: 17,
        slots: [{ id: "w4", title: "Mobility + core", time: "9:30 AM", kind: "recovery" }],
      },
      {
        day: "Thu",
        date: 18,
        slots: [{ id: "w5", title: "Match-play set", time: "11:00 AM", kind: "match" }],
      },
      {
        day: "Fri",
        date: 19,
        slots: [{ id: "w6", title: "Strength block", time: "8:00 AM", kind: "training" }],
      },
      {
        day: "Sat",
        date: 20,
        today: true,
        slots: [
          { id: "w7", title: "Serve precision", time: "9:00 AM", kind: "training" },
          { id: "w8", title: "Light hit", time: "3:00 PM", kind: "training" },
        ],
      },
      {
        day: "Sun",
        date: 21,
        slots: [{ id: "w9", title: "Rest + recovery", time: "All day", kind: "recovery" }],
      },
    ],
  },

  schedule: {
    events: [
      { id: "e1", title: "San Jose Open · R1", date: "Jul 2", location: "San Jose, CA", kind: "tournament" },
      { id: "e2", title: "Travel → San Jose", date: "Jun 30", location: "Flight · 2h 15m", kind: "travel" },
      { id: "e3", title: "Tune-up exhibition", date: "Jun 24", location: "Oakland TC", kind: "match" },
      { id: "e4", title: "Serve clinic w/ coach", date: "Jun 22", location: "Home club", kind: "training" },
    ],
    travelChecklist: [
      { id: "c1", label: "Confirm hotel near venue", done: true },
      { id: "c2", label: "Restring 3 rackets", done: false },
      { id: "c3", label: "Knee support + recovery kit", done: false },
      { id: "c4", label: "Submit player entry form", done: true },
    ],
  },

  sponsorship: [
    {
      id: "sp1",
      brand: "Baseline Athletics",
      category: "Apparel",
      fitScore: 92,
      reason: "Sponsors rising ITF singles players; audience overlap is strong.",
      status: "Suggested",
    },
    {
      id: "sp2",
      brand: "ReGen Recovery",
      category: "Wellness tech",
      fitScore: 87,
      reason: "Your recovery storyline is on-brand for their athlete program.",
      status: "Drafted",
    },
    {
      id: "sp3",
      brand: "CourtGrip",
      category: "Equipment",
      fitScore: 74,
      reason: "Regional grip brand looking for hard-court ambassadors.",
      status: "In review",
    },
  ],

  // Agent-produced insights — the legible face of the autonomous agent layer.
  // The first is the Orchestrator's headline recommendation (featured); the
  // rest are per-agent updates. Each can pipe a question into the AI panel.
  insights: [
    {
      id: "i0",
      agent: "Orchestrator",
      status: "ai",
      icon: "Sparkles",
      title: "Recommended next action",
      body: "Across recovery, training and schedule, the highest-leverage move this week is load management before San Jose.",
      suggestion: "Swap Friday's peak block for technical serve work and bank one recovery day.",
      action: { label: "Apply to plan", prompt: "Generate next week's plan with a lighter load.", replyId: "p9" },
    },
    {
      id: "i1",
      agent: "Recovery",
      status: "warning",
      icon: "HeartPulse",
      title: "Right-knee risk pattern",
      body: "Soreness logged after 3 of the last 4 sessions while weekly load rose 18%. The signal is trending up, not settling.",
      suggestion: "Suggested adjustment: a lighter day this week and a recovery block before the exhibition.",
      action: { label: "Check recovery risk", prompt: "Check my recovery risk.", replyId: "p3" },
    },
    {
      id: "i2",
      agent: "Scout",
      status: "positive",
      icon: "TrendingUp",
      title: "Serve trend improving",
      body: "First-serve percentage climbed 58% → 67% over your last 5 sessions, even as recovery dipped.",
      suggestion: "Hold the gains by keeping serve work technical rather than high-load.",
      action: { label: "Explain trend", prompt: "Explain my recent performance trend.", replyId: "p6" },
    },
    {
      id: "i3",
      agent: "Logistics",
      status: "warning",
      icon: "Plane",
      title: "Pre-tournament prep is behind",
      body: "San Jose Open is 12 days out — 3 rackets unstrung and no recovery slot booked for travel week.",
      suggestion: "Restring this week and block a mobility session the day before R1.",
      action: { label: "Plan travel", prompt: "Plan my travel and prep for the San Jose Open.", replyId: "p7" },
    },
    {
      id: "i4",
      agent: "Scout",
      status: "ai",
      icon: "Handshake",
      title: "Sponsor fit: Baseline Athletics",
      body: "92% brand fit — they back rising ITF singles players and your audience overlaps strongly.",
      suggestion: "Draft a short pitch using your recent 3W/2L run as proof points.",
      action: { label: "Draft email", prompt: "Draft a sponsorship email to Baseline Athletics.", replyId: "p4" },
    },
  ],

  suggestedPrompts: [
    { id: "p1", text: "What should I focus on next week?", section: "Overview" },
    { id: "p6", text: "Explain my performance trend", section: "Performance" },
    { id: "p3", text: "Check my recovery risk", section: "Recovery" },
    { id: "p5", text: "Summarize my last 7 days", section: "Training" },
    { id: "p8", text: "Find my next tournament", section: "Schedule" },
    { id: "p4", text: "Draft a sponsorship email", section: "Sponsorship" },
  ],
};

// NOTE: the old `cannedReplies` mock was removed — the AI chat now calls the
// real orchestrator (POST /orchestrator/chat). See Frontend/src/lib/api.ts.
