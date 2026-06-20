/**
 * Domain types for the Athlete Analytics OS.
 *
 * These mirror the backend contract in `framework_draft.md` so the mock data
 * in `data/mockAthleteData.ts` can later be swapped for real API responses
 * (`/entries`, `/metrics`, `/progress`, `/chat`, `/calendar`) with no UI change.
 */

/** Backend section enum — single source of truth, mirrors `SECTIONS`. */
export type Section =
  | "performance"
  | "injury_log"
  | "coaching"
  | "energy_nutrition"
  | "logistics"
  | "training";

/** Semantic status drives every accent color. Never color for decoration. */
export type Status = "positive" | "warning" | "negative" | "neutral" | "ai";

/** Which uAgent produced a given insight — makes the agent layer legible. */
export type AgentName = "Librarian" | "Recovery" | "Logistics" | "Scout" | "Orchestrator";

export interface AthleteProfile {
  name: string;
  sport: string;
  level: string;
  handle: string;
  currentWeek: string;
  avatarInitials: string;
  worldRank?: number;
}

export interface OverviewMetric {
  id: string;
  label: string;
  value: string;
  detail: string;
  status: Status;
  /** lucide icon name resolved in the component layer */
  icon: string;
}

/** Season-level goal — surfaced in the hero + as the "Main Goal" overview tile. */
export interface SeasonGoal {
  title: string;
  target: string;
  progressPct: number; // 0-100
  detail: string;
}

/**
 * A raw athlete brain-dump (voice / notebook photo / text) after the Librarian
 * agent has filed it. This is the product's core story made legible: messy
 * input → structured sections.
 */
export interface Intake {
  capturedAt: string; // relative, e.g. "2h ago"
  sources: ("voice" | "notebook" | "text")[];
  summary: string; // a short snippet of the raw log
  agent: AgentName; // who filed it (Librarian)
  filed: { label: string; status: Status }[]; // what got filed where
}

/** A point on the main performance chart (one per training day). */
export interface PerformancePoint {
  date: string; // short label e.g. "Mon"
  trainingLoad: number; // 0-100 normalized load
  recoveryScore: number; // 0-100, mirrors backend recovery_score
  matchPerformance: number | null; // 0-100, null on non-match days
}

export interface TrainingSession {
  id: string;
  date: string;
  focus: string;
  durationMin: number;
  intensity: "Low" | "Moderate" | "High" | "Peak";
  section: Section;
}

export interface MatchResult {
  id: string;
  date: string;
  opponent: string;
  result: "W" | "L";
  score: string;
  note: string;
}

/** A recent match plotted on the win/loss form graph. */
export interface FormMatch {
  id: string;
  label: string; // short date label for the x-axis
  opponent: string;
  result: "W" | "L";
  score: string;
  value: number; // 0-100 performance, drives bar height
}

export interface RecoverySignal {
  /** wellness language only — never medical diagnosis */
  risk: Status;
  riskLabel: string;
  sorenessTrend: { day: string; value: number }[];
  fatigueLevel: number; // 0-100
  sleepHours: number;
  focusArea: string;
}

export interface CalendarEvent {
  id: string;
  title: string;
  date: string;
  location: string;
  kind: "match" | "tournament" | "travel" | "training";
}

export interface SponsorshipLead {
  id: string;
  brand: string;
  category: string;
  fitScore: number; // 0-100
  reason: string;
  status: "Drafted" | "Suggested" | "In review";
}

/** A produced-by-an-agent insight surfaced on a panel / the insights strip. */
export interface AgentInsight {
  id: string;
  agent: AgentName;
  status: Status;
  title: string;
  body: string;
  suggestion: string;
  /** lucide icon name resolved in the component layer */
  icon?: string;
  /** optional one-tap action that pipes a question into the AI panel */
  action?: { label: string; prompt: string; replyId?: string };
}

export interface ChatPrompt {
  id: string;
  text: string;
  /** the dashboard section this prompt is connected to */
  section: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  sources?: string[];
}

export interface AthleteData {
  profile: AthleteProfile;
  goal: SeasonGoal;
  intake: Intake;
  overview: OverviewMetric[];
  performance: PerformancePoint[];
  training: {
    sessions: TrainingSession[];
    weeklyTotalMin: number;
    suggestedFocus: string;
  };
  matches: MatchResult[];
  form: FormMatch[];
  recovery: RecoverySignal;
  schedule: {
    events: CalendarEvent[];
    travelChecklist: { id: string; label: string; done: boolean }[];
  };
  sponsorship: SponsorshipLead[];
  insights: AgentInsight[];
  suggestedPrompts: ChatPrompt[];
}
