/**
 * Backend agent registry — the REAL agents, derived from `Backend/agents/` and
 * the orchestrator's routing labels in `services/orchestrator_service.py`.
 *
 * The Live Agent visualization renders ONLY the agents that actually ran for a
 * message (from the backend `agent_trace`), so every label here maps to a real
 * backend module — no invented "Flight Agent" / "Hotel Agent" nodes. Flights and
 * hotels are *option kinds* the Logistics agent prices, not separate agents.
 *
 *   orchestrator  agents/orchestrator.py        — classifies intent, routes
 *   athlete_context services/athlete_context.py — loads backend athlete context
 *   assistant     ask route · answer_question   — RAG over your logged history
 *   recovery      agents/recovery.py
 *   performance   agents/performance.py
 *   sponsorship   agents/sponsorship.py
 *   logistics     agents/logistics.py           — emitted as "travel" in agents_used
 *   librarian     agents/librarian.py           — files a brain-dump into sections
 *   scout         agents/scout.py               — tournament finder (defined)
 *   fitness       agents/fitness.py             — training-plan adjust (defined)
 *   coaching      agents/coaching.py            — tactical coaching (defined)
 *   payment       services/booking_service.py   — Stripe checkout (real event only)
 *   calendar      agents/calandar_client.py     — schedule sync (real event only)
 *
 * `payment` + `calendar` are runtime stages that light ONLY from real
 * Stripe/calendar events on the client (see LiveAgentPanel) — never inferred.
 */
import {
  CalendarDays,
  ClipboardList,
  Compass,
  CreditCard,
  Database,
  Dumbbell,
  Handshake,
  HeartPulse,
  Library,
  Plane,
  Sparkles,
  TrendingUp,
  Workflow,
  type LucideIcon,
} from "lucide-react";

export type AgentId =
  | "orchestrator"
  | "athlete_context"
  | "assistant"
  | "recovery"
  | "performance"
  | "sponsorship"
  | "logistics"
  | "librarian"
  | "scout"
  | "fitness"
  | "coaching"
  | "payment"
  | "calendar";

/** orchestrator anchors the center; runtime nodes only light on real events. */
export type AgentTone = "orchestrator" | "specialist" | "runtime";

export interface AgentMeta {
  id: AgentId;
  /** real backend agent name, shown as the node label */
  label: string;
  /** terse label rendered under the node */
  shortLabel: string;
  description: string;
  icon: LucideIcon;
  tone: AgentTone;
  /** the backend module this node reflects — kept honest in tooltips */
  source: string;
  /** short human label for the flow when this is the lead specialist */
  flow: string;
}

export const AGENT_REGISTRY: AgentMeta[] = [
  {
    id: "orchestrator",
    label: "Orchestrator",
    shortLabel: "Orchestrator",
    description: "Reads your request, classifies intent, and routes it to the right specialist.",
    icon: Workflow,
    tone: "orchestrator",
    source: "agents/orchestrator.py",
    flow: "Coordinating",
  },
  {
    id: "athlete_context",
    label: "Athlete Context",
    shortLabel: "Context",
    description: "Loads the athlete's backend profile, history, metrics, and calendar context.",
    icon: Database,
    tone: "runtime",
    source: "services/athlete_context.py",
    flow: "Loading context",
  },
  {
    id: "assistant",
    label: "Assistant",
    shortLabel: "Assistant",
    description: "Answers from your own logged history (RAG over your records).",
    icon: Sparkles,
    tone: "specialist",
    source: "ask route · answer_question",
    flow: "Answering from your history",
  },
  {
    id: "recovery",
    label: "Recovery",
    shortLabel: "Recovery",
    description: "Assesses recovery and overtraining signals as wellness guidance.",
    icon: HeartPulse,
    tone: "specialist",
    source: "agents/recovery.py",
    flow: "Recovery analysis",
  },
  {
    id: "performance",
    label: "Performance",
    shortLabel: "Performance",
    description: "Analyzes match and training trends to surface form changes.",
    icon: TrendingUp,
    tone: "specialist",
    source: "agents/performance.py",
    flow: "Performance analysis",
  },
  {
    id: "sponsorship",
    label: "Sponsorship",
    shortLabel: "Sponsor",
    description: "Finds sponsor fit and drafts outreach — draft only, never auto-sent.",
    icon: Handshake,
    tone: "specialist",
    source: "agents/sponsorship.py",
    flow: "Sponsorship draft",
  },
  {
    id: "logistics",
    label: "Logistics",
    shortLabel: "Logistics",
    description: "Plans travel and prices flight, hotel, and entry options from your schedule.",
    icon: Plane,
    tone: "specialist",
    source: "agents/logistics.py",
    flow: "Travel plan",
  },
  {
    id: "librarian",
    label: "Librarian",
    shortLabel: "Librarian",
    description: "Classifies a brain-dump and files each piece into the right section.",
    icon: Library,
    tone: "specialist",
    source: "agents/librarian.py",
    flow: "Filing your note",
  },
  {
    id: "scout",
    label: "Scout",
    shortLabel: "Scout",
    description: "Finds upcoming tournaments and events that fit your schedule.",
    icon: Compass,
    tone: "specialist",
    source: "agents/scout.py",
    flow: "Event scouting",
  },
  {
    id: "fitness",
    label: "Fitness",
    shortLabel: "Fitness",
    description: "Adjusts your training plan around current load and recovery.",
    icon: Dumbbell,
    tone: "specialist",
    source: "agents/fitness.py",
    flow: "Fitness plan",
  },
  {
    id: "coaching",
    label: "Coaching",
    shortLabel: "Coaching",
    description: "Turns performance gaps into tactical coaching advice.",
    icon: ClipboardList,
    tone: "specialist",
    source: "agents/coaching.py",
    flow: "Coaching",
  },
  {
    id: "payment",
    label: "Payment",
    shortLabel: "Payment",
    description: "Opens secure Stripe checkout — nothing is charged until you confirm.",
    icon: CreditCard,
    tone: "runtime",
    source: "services/booking_service.py (Stripe)",
    flow: "Booking",
  },
  {
    id: "calendar",
    label: "Calendar",
    shortLabel: "Calendar",
    description: "Adds confirmed bookings and events to your schedule.",
    icon: CalendarDays,
    tone: "runtime",
    source: "agents/calandar_client.py",
    flow: "Booking",
  },
];

export const ORCHESTRATOR_ID: AgentId = "orchestrator";

export const AGENT_BY_ID: Record<AgentId, AgentMeta> = AGENT_REGISTRY.reduce(
  (acc, meta) => {
    acc[meta.id] = meta;
    return acc;
  },
  {} as Record<AgentId, AgentMeta>
);

/** Registry index — used to keep formation positions STABLE across messages. */
export function agentIndex(id: AgentId): number {
  const i = AGENT_REGISTRY.findIndex((m) => m.id === id);
  return i === -1 ? AGENT_REGISTRY.length : i;
}

/**
 * Backend label → AgentId. The orchestrator emits a few aliases:
 *   "travel" → logistics · "ask"/"assistant" → assistant · "log" → librarian
 * Unknown labels resolve to null and are simply not rendered.
 */
const LABEL_TO_ID: Record<string, AgentId> = {
  orchestrator: "orchestrator",
  orchestratoragent: "orchestrator",
  "orchestrator agent": "orchestrator",
  athlete_context: "athlete_context",
  athletecontextservice: "athlete_context",
  "athlete context service": "athlete_context",
  "athlete context": "athlete_context",
  context: "athlete_context",
  assistant: "assistant",
  chatagent: "assistant",
  "chat agent": "assistant",
  ask: "assistant",
  recovery: "recovery",
  recoveryagent: "recovery",
  "recovery agent": "recovery",
  performance: "performance",
  performanceagent: "performance",
  "performance agent": "performance",
  sponsorship: "sponsorship",
  sponsorshipagent: "sponsorship",
  "sponsorship agent": "sponsorship",
  logistics: "logistics",
  logisticsagent: "logistics",
  "logistics agent": "logistics",
  travel: "logistics",
  librarian: "librarian",
  librarianagent: "librarian",
  "librarian agent": "librarian",
  log: "librarian",
  scout: "scout",
  scoutagent: "scout",
  "scout agent": "scout",
  fitness: "fitness",
  fitnessagent: "fitness",
  "fitness agent": "fitness",
  coaching: "coaching",
  coachingagent: "coaching",
  "coaching agent": "coaching",
  payment: "payment",
  paymentagent: "payment",
  "payment agent": "payment",
  calendar: "calendar",
  calendaragent: "calendar",
  "calendar agent": "calendar",
};

export function resolveAgentId(label?: string | null): AgentId | null {
  if (!label) return null;
  return LABEL_TO_ID[label.trim().toLowerCase()] ?? null;
}

/** Human flow label from the agents involved (the lead specialist wins). */
export function flowLabelFor(agents: AgentId[]): string | null {
  const lead = agents.find((id) => id !== "orchestrator" && AGENT_BY_ID[id]?.tone === "specialist");
  if (lead) return AGENT_BY_ID[lead].flow;
  if (agents.includes("payment") || agents.includes("calendar")) return "Booking";
  if (agents.includes("orchestrator")) return "Coordinating";
  return null;
}
