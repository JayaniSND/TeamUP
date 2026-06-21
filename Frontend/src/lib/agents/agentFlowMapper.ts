/**
 * Inferred fallback for the Live Agent network.
 *
 * The backend now returns a real `agent_trace` for every reply, so this is only
 * used when a message has no trace (old/cached messages, or a pre-reply error).
 * It builds a tiny SYNTHETIC trace using REAL backend agent ids so it flows
 * through the exact same parser/renderer as the live trace — just labelled as
 * inferred in the status box.
 */
import { AGENT_BY_ID, resolveAgentId, type AgentId } from "./backendAgentRegistry";
import type { AgentTraceEntry } from "@/types/athlete";

const RECOVERY_RE =
  /\b(recovery|recover|injur|soreness|sore|fatigue|tired|sleep|overtrain|rest|wellness|risk)\b/;
const PERFORMANCE_RE =
  /\b(performance|perform|form|stats|statistics|trend|progress|serve|match|result|win|los[es]|score)\b/;
const SPONSOR_RE = /\b(sponsor|sponsorship|brand|endorse|endorsement|deal|partnership)\b/;
const TRAVEL_RE =
  /\b(travel|trip|flight|flights|fly|airfare|airline|airport|hotel|hotels|stay|room|book|logistics|commute|journey)\b/;

/** Pick the one specialist the orchestrator most likely used. */
function pickSpecialist(text: string, agentsUsed?: string[]): AgentId | null {
  // Prefer the real metadata the reply carried.
  for (const label of agentsUsed ?? []) {
    const id = resolveAgentId(label);
    if (id && id !== "orchestrator") return id;
  }
  const t = (text || "").toLowerCase();
  if (TRAVEL_RE.test(t)) return "logistics";
  if (SPONSOR_RE.test(t)) return "sponsorship";
  if (RECOVERY_RE.test(t)) return "recovery";
  if (PERFORMANCE_RE.test(t)) return "performance";
  return null;
}

/** Build a synthetic, clearly-inferred trace (orchestrator → one specialist). */
export function inferTrace(text: string, agentsUsed?: string[]): AgentTraceEntry[] {
  const specialist = pickSpecialist(text, agentsUsed);
  const t0 = Date.now();
  const trace: AgentTraceEntry[] = [
    { agent: "orchestrator", status: "started", step: "Understanding your request", ts: t0 },
  ];
  if (specialist) {
    const label = AGENT_BY_ID[specialist].label;
    trace.push({
      from: "orchestrator",
      to: specialist,
      status: "in_progress",
      step: `Working with ${label}`,
      ts: t0 + 1,
    });
    trace.push({
      from: "orchestrator",
      to: specialist,
      status: "completed",
      step: `${label} ready`,
      ts: t0 + 2,
    });
  }
  trace.push({ agent: "orchestrator", status: "completed", step: "Composing your answer", ts: t0 + 3 });
  return trace;
}
