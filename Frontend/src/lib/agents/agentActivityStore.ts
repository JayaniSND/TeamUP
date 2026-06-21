/**
 * Shared runtime state for the Live Agent Network on the assistant page.
 *
 * A tiny module-level store (no extra dependency) read through React 18's
 * `useSyncExternalStore`. Unlike the old fixed-orbit model, this holds a
 * DYNAMIC set of agents: only the agents that actually ran for the current
 * message are present, plus the connections between the ones communicating.
 *
 * SOURCE OF TRUTH:
 *   The orchestrator now returns a real `agent_trace` (see
 *   services/orchestrator_service.py) describing the Orchestrator → specialist
 *   hand-off. The driver replays that trace into this store (`source: "trace"`).
 *   When a message has no trace (old/cached, or a pre-reply error) the driver
 *   falls back to a small inferred trace (`source: "inferred"`). The booking
 *   `payment`/`calendar` stages are appended ONLY from real Stripe/calendar
 *   events. `setAgentActivity` is the single seam any driver writes through.
 */
import { useSyncExternalStore } from "react";
import {
  AGENT_BY_ID,
  AGENT_REGISTRY,
  flowLabelFor,
  resolveAgentId,
  type AgentId,
  type AgentMeta,
} from "./backendAgentRegistry";
import type { AgentTraceEntry } from "@/types/athlete";

export { AGENT_BY_ID };
export type { AgentId } from "./backendAgentRegistry";
export type AgentNodeMeta = AgentMeta;

export type AgentActivityStatus = "idle" | "planned" | "in_progress" | "completed" | "error";

// Status precedence for inactive states. `in_progress` is intentionally allowed
// to override `completed` because the orchestrator participates in several
// separate steps during one message: routing, specialist calls, and final
// response composition.
const STATUS_RANK: Record<AgentActivityStatus, number> = {
  idle: 0,
  planned: 1,
  in_progress: 2,
  completed: 3,
  error: 4,
};
const mergeStatus = (
  cur: AgentActivityStatus | undefined,
  next: AgentActivityStatus
): AgentActivityStatus => {
  const current = cur ?? "idle";
  if (current === "error") return "error";
  if (next === "in_progress") return "in_progress";
  if (next === "planned" && current !== "idle" && current !== "planned") return current;
  return STATUS_RANK[next] >= STATUS_RANK[current] ? next : current;
};

/** A communication line between two agents that are actually talking. */
export interface AgentConnection {
  from: AgentId;
  to: AgentId;
  status: AgentActivityStatus;
}

/** Where the current activity came from — drives honest status-box copy.
 * "planned" = the optimistic pre-call prediction; "trace" = real backend events. */
export type AgentActivitySource = "idle" | "planned" | "trace" | "inferred";

export interface AgentActivityState {
  currentFlowId: string | null;
  currentMessageId: string | null;
  latestEvent: string | null;
  /** overall status of the current message flow */
  status: AgentActivityStatus;
  /** human step label shown in the status box */
  activeStep: string;
  /** the single strongly-highlighted agent (pulses) */
  activeAgent: AgentId | null;
  /** ONLY these agents render — recalculated per message */
  agents: AgentId[];
  /** per-node status for the agents above */
  nodeStatus: Partial<Record<AgentId, AgentActivityStatus>>;
  /** lines drawn only between agents actually communicating */
  connections: AgentConnection[];
  /** human label for the flow, e.g. "Recovery analysis" */
  currentFlow: string | null;
  source: AgentActivitySource;
  lastUpdated: number;
}

export const IDLE_STEP = "Waiting for your request";
export const ORCHESTRATOR = AGENT_BY_ID.orchestrator;
export const ORBIT_AGENTS = AGENT_REGISTRY.filter((agent) => agent.id !== "orchestrator");

const initialState: AgentActivityState = {
  currentFlowId: null,
  currentMessageId: null,
  latestEvent: null,
  status: "idle",
  activeStep: IDLE_STEP,
  activeAgent: null,
  agents: [],
  nodeStatus: {},
  connections: [],
  currentFlow: null,
  source: "idle",
  lastUpdated: 0,
};

let state: AgentActivityState = initialState;
let seenEventIds = new Set<string>();
const listeners = new Set<() => void>();

function emit() {
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Stable snapshot — the reference only changes when state changes. */
function getSnapshot(): AgentActivityState {
  return state;
}

export function getAgentActivitySnapshot(): AgentActivityState {
  return state;
}

/**
 * Generic dispatch. Accepts a partial patch or an updater. This is the seam the
 * trace/inferred/real-event drivers all write through.
 */
export function setAgentActivity(
  patch:
    | Partial<AgentActivityState>
    | ((prev: AgentActivityState) => Partial<AgentActivityState>)
): void {
  const next = typeof patch === "function" ? patch(state) : patch;
  state = { ...state, ...next, lastUpdated: Date.now() };
  emit();
}

/** Return to the idle resting state. */
export function resetAgentActivity(): void {
  state = { ...initialState, lastUpdated: Date.now() };
  seenEventIds = new Set();
  emit();
}

/**
 * Render the PLANNED agent network the instant a message is sent — the predicted
 * orchestrator → specialist edges — so the graph shows the whole expected workflow
 * up front, before any backend round-trip. Nodes start "planned" (dim/pending) and
 * are advanced to in_progress/completed as the real live trace arrives. Marked
 * `source: "planned"` so the panel knows real events haven't streamed yet.
 */
export function seedPlannedFlow(flowId: string, messageId: string, planned: AgentId[]): void {
  seenEventIds = new Set();
  const agents: AgentId[] = ["orchestrator"];
  const nodeStatus: Partial<Record<AgentId, AgentActivityStatus>> = { orchestrator: "in_progress" };
  const connections: AgentConnection[] = [];
  const targets = planned.length ? planned : (["assistant"] as AgentId[]);
  let firstTarget: AgentId | null = null;

  for (const id of targets) {
    if (!id || id === "orchestrator" || agents.includes(id)) continue;
    if (!firstTarget) firstTarget = id;
    agents.push(id);
    const status = id === firstTarget ? "in_progress" : "planned";
    nodeStatus[id] = status;
    connections.push({ from: "orchestrator", to: id, status });
  }
  state = {
    ...initialState,
    currentFlowId: flowId,
    currentMessageId: messageId,
    status: "in_progress",
    activeStep: firstTarget ? "Starting live agent workflow" : "Planning which agents to use",
    activeAgent: firstTarget ?? "orchestrator",
    agents,
    nodeStatus,
    connections,
    currentFlow: flowLabelFor(agents),
    source: "planned",
    lastUpdated: Date.now(),
  };
  emit();
}

const statusFrom = (value?: string): AgentActivityStatus =>
  value === "completed"
    ? "completed"
    : value === "error"
      ? "error"
      : value === "planned"
        ? "planned"
        : "in_progress";

const connectionKey = (from: AgentId, to: AgentId) => [from, to].sort().join("<->");

export function applyAgentTraceEvent(entry: AgentTraceEntry): void {
  if (entry.flowId && state.currentFlowId && entry.flowId !== state.currentFlowId) return;
  if (entry.eventId) {
    if (seenEventIds.has(entry.eventId)) return;
    seenEventIds.add(entry.eventId);
  }

  const status = statusFrom(entry.status);
  const completed = entry.type === "final_response_completed";
  let from = resolveAgentId(entry.from) ?? resolveAgentId(entry.fromAgent);
  let to = resolveAgentId(entry.to) ?? resolveAgentId(entry.toAgent);
  const node = resolveAgentId(entry.agent) ?? resolveAgentId(entry.agentName);
  const responding = entry.type === "agent_response_received";
  const composing = entry.type === "final_response_started";
  // A pre-call PLAN event (orchestrator predicting which agents it will use) — it
  // seeds nodes/edges but does NOT count as real activity having streamed yet.
  const isPlan =
    status === "planned" || entry.type === "agent_planned" || entry.type === "orchestrator_plan";

  setAgentActivity((prev) => {
    const agents = [...prev.agents];
    const add = (id: AgentId | null | undefined) => {
      if (id && !agents.includes(id)) agents.push(id);
    };

    const nodeStatus = { ...prev.nodeStatus };
    const connectionMap = new Map<string, AgentConnection>();
    for (const conn of prev.connections) connectionMap.set(connectionKey(conn.from, conn.to), conn);

    let activeAgent: AgentId | null = prev.activeAgent;
    if (composing && (!from || !to)) {
      const lastRealConnection = [...prev.connections]
        .reverse()
        .find((c) => c.from !== "orchestrator" || c.to !== "orchestrator");
      const peer =
        lastRealConnection?.from === "orchestrator"
          ? lastRealConnection.to
          : lastRealConnection?.from ??
            agents.find((id) => id !== "orchestrator" && nodeStatus[id] && nodeStatus[id] !== "planned");
      if (peer) {
        from = peer;
        to = "orchestrator";
      }
    }

    if (from && to) {
      add(from);
      add(to);
      const key = connectionKey(from, to);
      const existing = connectionMap.get(key);
      const mergedConn = composing && status === "in_progress" ? "in_progress" : mergeStatus(existing?.status, status);
      connectionMap.set(key, { from: existing?.from ?? from, to: existing?.to ?? to, status: mergedConn });
      const target = responding ? from : to;
      nodeStatus[target] = composing && status === "in_progress" ? "in_progress" : mergeStatus(nodeStatus[target], status);
      if (status === "in_progress") {
        if (!responding) {
          nodeStatus[from] = composing ? "in_progress" : mergeStatus(nodeStatus[from], "in_progress");
        }
        activeAgent = target;
      } else if (status === "completed") {
        if (completed || activeAgent === target) activeAgent = null;
      }
      // planned/idle: keep the orchestrator pulsing; don't promote a planned node.
    } else if (node) {
      add(node);
      nodeStatus[node] = mergeStatus(nodeStatus[node], status);
      if (status === "in_progress") activeAgent = node;
      else if (status === "completed" && (completed || activeAgent === node)) activeAgent = null;
    }

    const errored = status === "error";
    const nextStatus: AgentActivityStatus = errored ? "error" : completed ? "completed" : "in_progress";

    // When the flow finishes, settle to a clean "done" state: DROP any predicted
    // node that never actually ran (still "planned") so the final picture shows only
    // the agents that really worked, then turn every survivor + line green
    // (preserving error). This is the "finished communicating" moment, right as the
    // answer lands.
    let outAgents = agents;
    let outNodeStatus = nodeStatus;
    let outConnections = [...connectionMap.values()];
    if (completed) {
      outAgents = agents.filter(
        (id) => id === "orchestrator" || (nodeStatus[id] && nodeStatus[id] !== "planned")
      );
      outNodeStatus = {};
      for (const id of outAgents) outNodeStatus[id] = nodeStatus[id] === "error" ? "error" : "completed";
      outConnections = outConnections
        .filter((c) => outAgents.includes(c.from) && outAgents.includes(c.to) && c.status !== "planned")
        .map((c) => (c.status === "error" ? c : { ...c, status: "completed" }));
    }
    const flow = flowLabelFor(outAgents) ?? prev.currentFlow;

    return {
      currentFlowId: entry.flowId ?? prev.currentFlowId,
      currentMessageId: entry.messageId ?? prev.currentMessageId,
      latestEvent: entry.type ?? prev.latestEvent,
      agents: outAgents,
      nodeStatus: outNodeStatus,
      connections: outConnections,
      activeAgent: completed ? null : activeAgent,
      activeStep: entry.step || prev.activeStep,
      status: nextStatus,
      currentFlow: flow,
      // A plan event keeps the prior source (still "planned"); only REAL activity
      // promotes the source to "trace" (what the panel uses to detect live streaming).
      source: isPlan ? prev.source : "trace",
    };
  });
}

export function applyAgentTraceEvents(trace: AgentTraceEntry[] | undefined): void {
  for (const event of trace ?? []) applyAgentTraceEvent(event);
}

/** React hook: subscribe a component to the activity store. */
export function useAgentActivity(): AgentActivityState {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

/** Node status, derived from the dynamic map (defaults to idle). */
export function nodeStatusFor(agentId: AgentId, activity: AgentActivityState): AgentActivityStatus {
  return activity.nodeStatus[agentId] ?? "idle";
}

/** Connection status for the legacy orbit renderer. */
export function lineStatusFor(agentId: AgentId, activity: AgentActivityState): AgentActivityStatus {
  const connection = activity.connections.find((item) => item.from === agentId || item.to === agentId);
  return connection?.status ?? nodeStatusFor(agentId, activity);
}
