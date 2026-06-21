/**
 * Turn the backend `agent_trace` into ordered, CUMULATIVE frames the Live Agent
 * driver replays over time. Each frame is a full snapshot of which agents are
 * present, their per-node status, and the connections between them — so the
 * network grows the formation step by step (Orchestrator → specialist → done).
 *
 * The same shape powers the inferred fallback (agentFlowMapper builds a tiny
 * synthetic trace), so there is exactly one rendering path.
 */
import type {
  AgentActivityState,
  AgentActivityStatus,
  AgentConnection,
} from "./agentActivityStore";
import { resolveAgentId, type AgentId } from "./backendAgentRegistry";
import type { AgentTraceEntry } from "@/types/athlete";

export type { AgentTraceEntry } from "@/types/athlete";

/** A single replayable snapshot (subset of the store state). */
export type TraceFrame = Pick<
  AgentActivityState,
  | "agents"
  | "nodeStatus"
  | "connections"
  | "activeAgent"
  | "activeStep"
  | "status"
  | "currentFlowId"
  | "currentMessageId"
  | "latestEvent"
>;

const mapStatus = (s?: string): AgentActivityStatus =>
  s === "completed" ? "completed" : s === "error" ? "error" : "in_progress";

const connKey = (from: AgentId, to: AgentId) => [from, to].sort().join("<->");

/**
 * Walk the trace, accumulating agents/nodeStatus/connections, emitting one frame
 * per entry, then a final "all completed" (or "error") frame so every line
 * settles green.
 */
export function parseTraceToFrames(trace: AgentTraceEntry[] | undefined): TraceFrame[] {
  if (!trace || trace.length === 0) return [];

  const agents: AgentId[] = [];
  const nodeStatus: Partial<Record<AgentId, AgentActivityStatus>> = {};
  const conns = new Map<string, AgentConnection>();
  const frames: TraceFrame[] = [];

  const add = (id: AgentId | null | undefined) => {
    if (id && !agents.includes(id)) agents.push(id);
  };

  const errored = trace.some((e) => e.status === "error");

  for (const entry of trace) {
    const status = mapStatus(entry.status);
    const from = resolveAgentId(entry.from) ?? resolveAgentId(entry.fromAgent);
    const to = resolveAgentId(entry.to) ?? resolveAgentId(entry.toAgent);
    const node = resolveAgentId(entry.agent) ?? resolveAgentId(entry.agentName);
    const responding = entry.type === "agent_response_received";
    let active: AgentId | null = null;

    if (from && to) {
      add(from);
      add(to);
      const key = connKey(from, to);
      const existing = conns.get(key);
      conns.set(key, { from: existing?.from ?? from, to: existing?.to ?? to, status });
      nodeStatus[responding ? from : to] = status;
      // The caller stays emphasized while it waits for the downstream response.
      if (!responding && status === "in_progress") {
        nodeStatus[from] = "in_progress";
      }
      active = status === "completed" ? null : responding ? from : to;
    } else if (node) {
      add(node);
      nodeStatus[node] = status;
      active = status === "in_progress" ? node : null;
    }

    frames.push({
      agents: [...agents],
      nodeStatus: { ...nodeStatus },
      connections: [...conns.values()],
      activeAgent: active,
      activeStep: entry.step || "",
      status: entry.status === "error" ? "error" : "in_progress",
      currentFlowId: entry.flowId ?? null,
      currentMessageId: entry.messageId ?? null,
      latestEvent: entry.type ?? null,
    });
  }

  // Final settle: everything completes (unless the flow errored).
  if (!errored) {
    for (const id of agents) nodeStatus[id] = "completed";
  }
  const finalConns = [...conns.values()].map((c) => ({
    ...c,
    status: errored ? c.status : ("completed" as AgentActivityStatus),
  }));
  const lastStep = trace[trace.length - 1]?.step;
  frames.push({
    agents: [...agents],
    nodeStatus: { ...nodeStatus },
    connections: finalConns,
    activeAgent: null,
    activeStep: errored ? "Agent communication needs attention" : lastStep || "Completed",
    status: errored ? "error" : "completed",
    currentFlowId: trace[trace.length - 1]?.flowId ?? null,
    currentMessageId: trace[trace.length - 1]?.messageId ?? null,
    latestEvent: trace[trace.length - 1]?.type ?? null,
  });

  return frames;
}
