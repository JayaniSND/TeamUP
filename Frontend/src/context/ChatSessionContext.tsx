import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MutableRefObject,
  type ReactNode,
} from "react";
import { useCalendarEvents } from "@/context/CalendarEventsContext";
import {
  ApiError,
  CHAT_SYSTEM_INSTRUCTIONS,
  agentActivityStreamUrl,
  sendChatMessage,
  type ChatMode,
} from "@/lib/api";
import { applyAgentTraceEvent, resetAgentActivity } from "@/lib/agents/agentActivityStore";
import {
  isPaymentSessionActive,
  restorePaymentSessionState,
  savePaymentSessionState,
} from "@/lib/paymentSessionState";
import type { ChatMessage, SharedCalendarEvent } from "@/types/athlete";

// Monotonic id generator shared by every surface that appends to the thread, so
// ids never collide between the greeting, the rail, and the full-page assistant.
let idSeq = 0;
export const nextChatId = () => `c${++idSeq}`;

interface ChatSessionContextValue {
  messages: ChatMessage[];
  loading: boolean;
  /** Send one message to the orchestrator. Singleton + guarded against double sends. */
  send: (text: string, opts?: { mode?: ChatMode }) => Promise<void>;
  /** Append a local assistant notice without calling the orchestrator. */
  appendAssistantMessage: (text: string) => void;
  /** Last externally-seeded question id processed, so co-mounted surfaces dedupe. */
  lastSeedIdRef: MutableRefObject<number>;
}

const ChatSessionContext = createContext<ChatSessionContextValue | null>(null);

const loadCheckoutMessages = (): ChatMessage[] | null => {
  if (!isPaymentSessionActive()) return null;
  const messages = restorePaymentSessionState()?.chatMessages;
  return Array.isArray(messages) && messages.length ? messages : null;
};

const loadCheckoutSessionId = () =>
  isPaymentSessionActive() ? restorePaymentSessionState()?.chatSessionId || "" : "";

const compactCalendarEvent = (event: SharedCalendarEvent) => ({
  id: event.id,
  title: event.title,
  type: event.type,
  startDate: event.startDate,
  startTime: event.startTime,
  endDate: event.endDate,
  endTime: event.endTime,
  location: event.location,
  source: event.source,
});

const DASHBOARD_REPLY_LIMIT = 360;
const DASHBOARD_REPLY_TOTAL_LIMIT = 400;
const DASHBOARD_DETAILS_LINE = "Open full chat for more details.";

const sentenceEnd = /[.!?]$/;

const truncateAtWord = (text: string, limit: number) => {
  if (text.length <= limit) return text;
  const clipped = text.slice(0, limit).replace(/\s+\S*$/, "").replace(/[,:;\s]+$/, "");
  return clipped || text.slice(0, limit).trim();
};

const compactDashboardReply = (text: string) => {
  const stripped = text
    .replace(/^(summary|best option|details|calendar plan|calendar update|other options|draft email|next step)\s*$/gim, "")
    .replace(/^\s*\*\s+/gm, "");
  const normalized = stripped.replace(/\s+/g, " ").trim();
  if (!normalized) return text;

  const sentences = normalized.match(/[^.!?]+(?:[.!?]+|$)/g)?.map((s) => s.trim()).filter(Boolean) ?? [
    normalized,
  ];
  const picked = sentences.slice(0, 3).join(" ").trim();
  const needsMore =
    sentences.length > 3 || normalized.length > DASHBOARD_REPLY_LIMIT || normalized.length > picked.length;

  let reply = truncateAtWord(picked, needsMore ? DASHBOARD_REPLY_TOTAL_LIMIT - DASHBOARD_DETAILS_LINE.length - 2 : DASHBOARD_REPLY_LIMIT);
  if (!sentenceEnd.test(reply)) reply = `${reply}.`;

  if (needsMore && !/open full chat/i.test(reply)) {
    reply = `${reply} ${DASHBOARD_DETAILS_LINE}`;
  }

  return reply;
};

const newRuntimeId = (prefix: string) =>
  globalThis.crypto?.randomUUID?.() ?? `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`;

function openAgentActivityStream(flowId: string, messageId: string) {
  if (typeof EventSource === "undefined") {
    return { eventSource: null, ready: Promise.resolve() };
  }

  const eventSource = new EventSource(agentActivityStreamUrl(flowId, messageId));
  eventSource.addEventListener("agent_activity", (event) => {
    try {
      applyAgentTraceEvent(JSON.parse((event as MessageEvent).data));
    } catch {
      // Ignore malformed activity events; chat response handling remains authoritative.
    }
  });

  let done = false;
  const ready = new Promise<void>((resolve) => {
    const finish = () => {
      if (done) return;
      done = true;
      resolve();
    };
    eventSource.onopen = finish;
    eventSource.onerror = finish;
    window.setTimeout(finish, 450);
  });

  return { eventSource, ready };
}

/**
 * Session-level home for the AI chat. The thread, the loading flag, and the
 * single send engine all live here so there is exactly ONE conversation no
 * matter how many surfaces render it — the compact dashboard rail (which App
 * mounts twice for responsive layouts) and the full-page assistant all share
 * this state. That means navigating between them, or booking + paying, keeps
 * every previous message.
 *
 * History is kept in React runtime state, except for a short checkout-only
 * snapshot used to survive the same-tab Stripe redirect. A normal browser
 * refresh resets the conversation to the greeting.
 *
 * Every message is forwarded to the single orchestrator endpoint
 * (lib/api.sendChatMessage); this engine never picks an agent — the backend
 * orchestrator decides which specialist(s) answer.
 */
export function ChatSessionProvider({
  greeting,
  children,
}: {
  greeting: string;
  children: ReactNode;
}) {
  const { events, pendingPayment } = useCalendarEvents();
  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    ...(loadCheckoutMessages() ?? [{ id: nextChatId(), role: "assistant", text: greeting }]),
  ]);
  const [loading, setLoading] = useState(false);

  const sessionIdRef = useRef<string>("");
  if (!sessionIdRef.current) {
    sessionIdRef.current =
      loadCheckoutSessionId() ||
      (globalThis.crypto?.randomUUID?.() ?? `s-${Date.now()}-${Math.random().toString(36).slice(2)}`);
  }

  // Live in-flight mirror so the guard reads the current value synchronously and
  // two co-mounted surfaces can't fire the same send twice.
  const inFlight = useRef(false);
  const abortRef = useRef<AbortController | null>(null);
  const lastSeedIdRef = useRef(0);

  const calendarContext = useMemo(() => {
    const today = new Date().toISOString().slice(0, 10);
    const sortedEvents = [...events].sort((a, b) =>
      `${a.startDate} ${a.startTime}`.localeCompare(`${b.startDate} ${b.startTime}`)
    );
    const currentMatch =
      sortedEvents.find((event) => event.type === "match" && event.startDate >= today) ??
      sortedEvents.find((event) => event.type === "match");

    return {
      currentMatch: currentMatch ? compactCalendarEvent(currentMatch) : null,
      events: sortedEvents.slice(0, 30).map(compactCalendarEvent),
    };
  }, [events]);

  useEffect(() => {
    if (pendingPayment) {
      savePaymentSessionState({
        chatMessages: messages,
        chatSessionId: sessionIdRef.current,
      });
    }
  }, [messages, pendingPayment]);

  const appendAssistantMessage = useCallback((text: string) => {
    const normalized = text.trim();
    if (!normalized) return;
    setMessages((m) => {
      if (m[m.length - 1]?.role === "assistant" && m[m.length - 1]?.text === normalized) return m;
      return [...m, { id: nextChatId(), role: "assistant", text: normalized }];
    });
  }, []);

  const send = useCallback(async (text: string, opts: { mode?: ChatMode } = {}) => {
    const question = text.trim();
    if (!question || inFlight.current) return; // ignore empty + duplicate sends
    const mode = opts.mode ?? "full";

    inFlight.current = true;
    setLoading(true);
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const flowId = newRuntimeId("flow");
    const messageId = newRuntimeId("msg");

    resetAgentActivity();
    const { eventSource, ready: streamReady } = openAgentActivityStream(flowId, messageId);

    setMessages((m) => [...m, { id: messageId, role: "user", text: question, flowId, messageId }]);

    try {
      await streamReady;
      // Forward only the message + identity/session/page — the orchestrator
      // decides which agent(s) handle it (incl. travel/booking).
      const reply = await sendChatMessage(question, {
        sessionId: sessionIdRef.current,
        flowId,
        messageId,
        mode,
        systemInstruction: CHAT_SYSTEM_INSTRUCTIONS[mode],
        context: {
          page: typeof window !== "undefined" ? window.location.pathname : "/",
          surface: mode,
          calendar: calendarContext,
        },
        signal: controller.signal,
      });
      // Backend sources are raw entry ids — surface them as one tidy grounding
      // chip rather than dumping UUIDs into the bubble.
      const n = reply.sources.length;
      const grounding = n ? [`Grounded in ${n} ${n === 1 ? "entry" : "entries"}`] : undefined;
      setMessages((m) => [
        ...m,
        {
          id: nextChatId(),
          role: "assistant",
          text: mode === "dashboard" ? compactDashboardReply(reply.message) : reply.message,
          sources: grounding,
          agents: reply.agentsUsed.length ? reply.agentsUsed : undefined,
          trace: reply.agentTrace.length ? reply.agentTrace : undefined,
          flowId: reply.flowId,
          messageId: reply.messageId,
          actions: reply.suggestedActions.length
            ? mode === "dashboard"
              ? reply.suggestedActions.slice(0, 2)
              : reply.suggestedActions
            : undefined,
          options: reply.options.length ? reply.options : undefined,
        },
      ]);
    } catch (e) {
      if ((e as Error)?.name === "AbortError") return; // superseded — drop silently
      const msg =
        e instanceof ApiError ? e.message : "Something went wrong reaching the AI. Please try again.";
      setMessages((m) => [
        ...m,
        {
          id: nextChatId(),
          role: "assistant",
          text: mode === "dashboard" ? compactDashboardReply(msg) : msg,
          isError: true,
        },
      ]);
    } finally {
      if (eventSource) {
        window.setTimeout(() => eventSource?.close(), 1000);
      }
      if (abortRef.current === controller) {
        inFlight.current = false;
        setLoading(false);
        abortRef.current = null;
      }
    }
  }, [calendarContext]);

  const value = useMemo<ChatSessionContextValue>(
    () => ({ messages, loading, send, appendAssistantMessage, lastSeedIdRef }),
    [appendAssistantMessage, loading, messages, send]
  );

  return <ChatSessionContext.Provider value={value}>{children}</ChatSessionContext.Provider>;
}

export function useChatSessionState() {
  const context = useContext(ChatSessionContext);
  if (!context) {
    throw new Error("useChatSessionState must be used inside ChatSessionProvider");
  }
  return context;
}
