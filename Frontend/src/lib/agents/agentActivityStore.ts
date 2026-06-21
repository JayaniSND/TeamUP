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

export type AgentActivityStatus = "idle" | "in_progress" | "completed" | "error";

/** A communication line between two agents that are actually talking. */
export interface AgentConnection {
  from: AgentId;
  to: AgentId;
  status: AgentActivityStatus;
}

/** Where the current activity came from — drives honest status-box copy. */
export type AgentActivitySource = "idle" | "trace" | "inferred";

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
  emit();
}

/**
 * Optimistically light the Orchestrator node the instant a message is sent, so
 * the graph reacts immediately — before the first live SSE event arrives. The
 * live stream then fills in the specialists as the backend actually calls them.
 * Seeds ONLY the orchestrator (a single node is not treated as "already
 * streamed"), so a failed stream still falls back to the real backend trace.
 */
export function seedFlow(flowId: string, messageId: string): void {
  state = {
    ...initialState,
    currentFlowId: flowId,
    currentMessageId: messageId,
    status: "in_progress",
    activeStep: "Routing your request",
    activeAgent: "orchestrator",
    agents: ["orchestrator"],
    nodeStatus: { orchestrator: "in_progress" },
    source: "trace",
    lastUpdated: Date.now(),
  };
  emit();
}

const statusFrom = (value?: string): AgentActivityStatus =>
  value === "completed" ? "completed" : value === "error" ? "error" : "in_progress";

const connectionKey = (from: AgentId, to: AgentId) => [from, to].sort().join("<->");

export function applyAgentTraceEvent(entry: AgentTraceEntry): void {
  const status = statusFrom(entry.status);
  const from = resolveAgentId(entry.from) ?? resolveAgentId(entry.fromAgent);
  const to = resolveAgentId(entry.to) ?? resolveAgentId(entry.toAgent);
  const node = resolveAgentId(entry.agent) ?? resolveAgentId(entry.agentName);
  const responding = entry.type === "agent_response_received";

  setAgentActivity((prev) => {
    const agents = [...prev.agents];
    const add = (id: AgentId | null | undefined) => {
      if (id && !agents.includes(id)) agents.push(id);
    };

    const nodeStatus = { ...prev.nodeStatus };
    const connectionMap = new Map<string, AgentConnection>();
    for (const conn of prev.connections) connectionMap.set(connectionKey(conn.from, conn.to), conn);

    let activeAgent: AgentId | null = prev.activeAgent;
    if (from && to) {
      add(from);
      add(to);
      const key = connectionKey(from, to);
      const existing = connectionMap.get(key);
      connectionMap.set(key, { from: existing?.from ?? from, to: existing?.to ?? to, status });
      const target = responding ? from : to;
      nodeStatus[target] = status;
      if (!responding && status === "in_progress") nodeStatus[from] = "in_progress";
      activeAgent = status === "completed" ? null : target;
    } else if (node) {
      add(node);
      nodeStatus[node] = status;
      activeAgent = status === "in_progress" ? node : null;
    }

    const completed = entry.type === "final_response_completed";
    const errored = status === "error";
    const nextStatus: AgentActivityStatus = errored ? "error" : completed ? "completed" : "in_progress";
    const flow = flowLabelFor(agents) ?? prev.currentFlow;

    // When the flow finishes, settle every participating node + line to completed
    // (green), preserving any error state. Without this, a fan-out parent left
    // mid-chain (e.g. Recovery after firing Fitness + Coaching) could linger
    // "in_progress" even though the whole workflow is done.
    let outNodeStatus = nodeStatus;
    let outConnections = [...connectionMap.values()];
    if (completed) {
      outNodeStatus = {};
      for (const id of agents) outNodeStatus[id] = nodeStatus[id] === "error" ? "error" : "completed";
      outConnections = outConnections.map((c) => (c.status === "error" ? c : { ...c, status: "completed" }));
    }

    return {
      currentFlowId: entry.flowId ?? prev.currentFlowId,
      currentMessageId: entry.messageId ?? prev.currentMessageId,
      latestEvent: entry.type ?? prev.latestEvent,
      agents,
      nodeStatus: outNodeStatus,
      connections: outConnections,
      activeAgent: completed ? null : activeAgent,
      activeStep: entry.step || prev.activeStep,
      status: nextStatus,
      currentFlow: flow,
      source: "trace",
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
