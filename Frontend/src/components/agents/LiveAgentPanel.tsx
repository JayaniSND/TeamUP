import { Suspense, lazy, useEffect, useRef, useState, type RefObject } from "react";
import { useReducedMotion } from "framer-motion";
import { Workflow } from "lucide-react";
import { useChatSessionState } from "@/context/ChatSessionContext";
import { useCalendarEvents } from "@/context/CalendarEventsContext";
import {
  setAgentActivity,
  getAgentActivitySnapshot,
  useAgentActivity,
  applyAgentTraceEvents,
  type AgentActivityState,
  type AgentConnection,
  type AgentId,
} from "@/lib/agents/agentActivityStore";
import type { ChatMessage } from "@/types/athlete";
import { AgentActivityStatus } from "./AgentActivityStatus";
import { AgentNetwork } from "./AgentNetwork";
import { AgentCanvasBoundary, supportsWebGL } from "./AgentCanvasBoundary";

// The Three.js scene is code-split so `three` never lands in the main bundle and
// only loads once the panel is actually on screen.
const AgentNetwork3D = lazy(() => import("./AgentNetwork3D"));

type NodeStatus = AgentActivityState["status"];

const dedupe = (ids: AgentId[]): AgentId[] => Array.from(new Set(ids));
const connKey = (from: AgentId, to: AgentId) => `${from}->${to}`;

/** Merge connections by from→to key (incoming wins). */
function mergeConns(prev: AgentConnection[], incoming: AgentConnection[]): AgentConnection[] {
  const map = new Map<string, AgentConnection>();
  for (const c of prev) map.set(connKey(c.from, c.to), c);
  for (const c of incoming) map.set(connKey(c.from, c.to), c);
  return [...map.values()];
}

interface ExtendOpts {
  add?: AgentId[];
  node?: Partial<Record<AgentId, NodeStatus>>;
  conn?: AgentConnection[];
  activeAgent: AgentId | null;
  activeStep: string;
  status: NodeStatus;
  flow?: string | null;
  source?: AgentActivityState["source"];
}

/** Extend the current state — used by the real Stripe/calendar booking stages. */
function extendState(prev: AgentActivityState, opts: ExtendOpts): Partial<AgentActivityState> {
  return {
    agents: dedupe([...prev.agents, ...(opts.add ?? [])]),
    nodeStatus: { ...prev.nodeStatus, ...(opts.node ?? {}) },
    connections: mergeConns(prev.connections, opts.conn ?? []),
    activeAgent: opts.activeAgent,
    activeStep: opts.activeStep,
    status: opts.status,
    currentFlow: opts.flow ?? prev.currentFlow,
    source: opts.source ?? (prev.source === "idle" ? "inferred" : prev.source),
  };
}

/**
 * Live activity driver. The Live Agent graph is driven IN REAL TIME by the SSE
 * stream (see ChatSessionContext.openAgentActivityStream → applyAgentTraceEvent),
 * which lights each agent and edge the instant the backend calls it. This hook
 * only handles the lifecycle AROUND that live stream:
 *   • when a reply lands, finalize the live formation and fade back to idle;
 *   • if the stream never delivered (EventSource unsupported/blocked), apply the
 *     REAL backend trace once — instantly, never a paced "replay after the
 *     response" and never a keyword-guessed fake;
 *   • append the booking payment/calendar stages ONLY from real Stripe/calendar
 *     events. It never touches the chat engine — it observes shared state.
 */
function useLiveAgentActivity() {
  const { messages, loading } = useChatSessionState();
  const { confirmation } = useCalendarEvents();

  const messagesRef = useRef<ChatMessage[]>(messages);
  messagesRef.current = messages;

  const prevLoadingRef = useRef(false);
  const prevConfirmationRef = useRef(confirmation);

  const timers = useRef<number[]>([]);
  const clearTimers = () => {
    timers.current.forEach((id) => window.clearTimeout(id));
    timers.current = [];
  };
  const later = (fn: () => void, ms: number) => {
    timers.current.push(window.setTimeout(fn, ms));
  };

  // ── chat: send + reply ────────────────────────────────────────────────────
  // The graph animates LIVE during the request via the SSE stream; this effect
  // only finalizes when the reply lands. It never paces a post-response replay.
  useEffect(() => {
    const wasLoading = prevLoadingRef.current;
    prevLoadingRef.current = loading;
    const msgs = messagesRef.current;

    if (!wasLoading && loading) {
      // New send — the live stream (seeded orchestrator + SSE events) drives the
      // store now. Just cancel any pending fade-to-idle from the previous reply.
      clearTimers();
      return;
    }

    // REPLY landed → finalize the live formation (do NOT replay it).
    if (wasLoading && !loading) {
      clearTimers();
      const lastAssistant = [...msgs].reverse().find((m) => m.role === "assistant");

      if (lastAssistant?.isError) {
        setAgentActivity((prev) => ({
          status: "error",
          activeStep: "Agent communication needs attention",
          activeAgent: prev.activeAgent ?? "orchestrator",
          nodeStatus: { ...prev.nodeStatus, [prev.activeAgent ?? "orchestrator"]: "error" },
        }));
        return;
      }

      const snap = getAgentActivitySnapshot();
      // The live SSE stream delivered if the store is on this reply's flow AND real
      // backend events promoted the source to "trace". We can't key off "a non-
      // orchestrator node exists" anymore, because the optimistic plan pre-seeds the
      // predicted specialists (source stays "planned" until real activity streams).
      const liveStreamed =
        !!lastAssistant?.flowId &&
        snap.currentFlowId === lastAssistant.flowId &&
        snap.source === "trace";

      // If the SSE stream never delivered, apply the REAL backend trace once —
      // instantly, never a paced post-response replay and never a fake.
      if (!liveStreamed && lastAssistant?.trace?.length) {
        applyAgentTraceEvents(lastAssistant.trace);
      }

      // Finalize the formation (live or trace) and fade the active agent away.
      setAgentActivity({ status: "completed", activeAgent: null });
    }
    // messages are read via ref; only the loading transition drives this.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading]);

  // ── real booking: payment → calendar (NOT inferred) ───────────────────────
  useEffect(() => {
    const prevConfirmation = prevConfirmationRef.current;
    prevConfirmationRef.current = confirmation;

    const newConfirmation = !!confirmation && confirmation !== prevConfirmation;

    // Payment succeeded → calendar updates → done. Driven by the REAL backend
    // checkout/confirmation trace (payment → calendar), applied as it stands.
    if (newConfirmation) {
      clearTimers();
      if (confirmation.trace?.length) {
        applyAgentTraceEvents(confirmation.trace);
        return;
      }
      setAgentActivity((prev) =>
        extendState(prev, {
          add: ["logistics", "payment", "calendar"],
          node: { payment: "completed", calendar: "in_progress" },
          conn: [
            { from: "logistics", to: "payment", status: "completed" },
            { from: "payment", to: "calendar", status: "in_progress" },
          ],
          activeAgent: "calendar",
          activeStep: "Updating your calendar",
          status: "in_progress",
          flow: prev.currentFlow ?? "Booking",
        })
      );
      later(
        () =>
          setAgentActivity((prev) =>
            extendState(prev, {
              node: { calendar: "completed" },
              conn: [{ from: "payment", to: "calendar", status: "completed" }],
              activeAgent: null,
              activeStep: "Booking added to your calendar",
              status: "completed",
            })
          ),
        1000
      );
      return;
    }

    // Selecting/canceling a local booking option is not a backend agent call.
    // PaymentAgent appears only from checkout/confirmation backend traces.
  }, [confirmation]);

  // Clear pending animation timers on unmount; the last completed formation
  // remains visible until the next user message resets the shared store.
  useEffect(() => clearTimers, []);
}

/** Observe visibility so the 3D scene pauses when off-screen or tab-hidden. */
function useVisibility(ref: RefObject<HTMLElement>) {
  const [inView, setInView] = useState(false);
  const [docVisible, setDocVisible] = useState(
    typeof document === "undefined" ? true : !document.hidden
  );

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }
    const io = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting), {
      threshold: 0.1,
    });
    io.observe(el);
    return () => io.disconnect();
  }, [ref]);

  useEffect(() => {
    const onVis = () => setDocVisible(!document.hidden);
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  return { inView, docVisible };
}

/**
 * Right-rail "Live Agent System" panel for the assistant page: a plain-text
 * status box above a live 3D agent network. Drives the shared activity store and
 * renders the Three.js scene (lazy-loaded, paused when not visible), falling back
 * to the SVG network under reduced-motion or if WebGL/3D is unavailable.
 */
export function LiveAgentPanel() {
  useLiveAgentActivity();
  const activity = useAgentActivity();

  const netRef = useRef<HTMLDivElement>(null);
  const { inView, docVisible } = useVisibility(netRef);
  const reducedMotion = useReducedMotion();

  // Mount the 3D scene eagerly in this panel. The user is here to watch the
  // live agent system, so waiting for a deep canvas well to intersect can make
  // the panel look static even while a request is running.
  const canUse3D = !reducedMotion && supportsWebGL();
  const paused = !inView || !docVisible || !!reducedMotion;

  return (
    <section className="glass-card fade-up flex min-h-0 min-w-0 flex-col rounded-[1.65rem] p-4 xl:flex-1 xl:max-h-full">
      <header className="flex shrink-0 items-center gap-2.5 border-b border-line pb-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-ai/20 to-accent/20 text-ai ring-1 ring-ai/30">
          <Workflow className="size-4.5" strokeWidth={2} />
        </span>
        <div className="min-w-0 leading-tight">
          <div className="text-sm font-semibold text-text">Live Agent System</div>
          <div className="text-[11px] text-text-muted">Only the agents working on your request</div>
        </div>
      </header>

      <div className="mt-3 shrink-0">
        <AgentActivityStatus activity={activity} />
      </div>

      <div
        ref={netRef}
        className="relative mt-3 flex h-[260px] min-h-[220px] min-w-0 grow items-center justify-center overflow-hidden rounded-[1.35rem] bg-[radial-gradient(circle_at_50%_18%,rgba(31,159,104,0.13),rgba(255,255,255,0.40)_42%,rgba(226,246,236,0.30)_100%)] ring-1 ring-line/80 sm:h-[300px] xl:h-auto xl:min-h-[260px]"
      >
        {canUse3D ? (
          <AgentCanvasBoundary fallback={<AgentNetwork activity={activity} />}>
            <Suspense fallback={<AgentNetwork activity={activity} />}>
              {/* Fill the whole well; the auto-fit camera frames the formation. */}
              <div className="absolute inset-0">
                <AgentNetwork3D activity={activity} paused={paused} />
              </div>
            </Suspense>
          </AgentCanvasBoundary>
        ) : (
          <AgentNetwork activity={activity} />
        )}
      </div>

      <div className="mt-3 flex shrink-0 flex-wrap items-center justify-center gap-x-4 gap-y-1 text-[10px] text-text-dim">
        <span className="flex items-center gap-1.5">
          <span className="h-[3px] w-3.5 rounded-full bg-ai" /> Engaging
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-[3px] w-3.5 rounded-full bg-negative" /> Communicating
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-[3px] w-3.5 rounded-full bg-positive" /> Done
        </span>
      </div>
    </section>
  );
}
