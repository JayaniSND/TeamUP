import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type MutableRefObject,
  type ReactNode,
} from "react";
import { useCalendarEvents } from "@/context/CalendarEventsContext";
import { ApiError, CHAT_SYSTEM_INSTRUCTIONS, sendChatMessage, type ChatMode } from "@/lib/api";
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
  /** Last externally-seeded question id processed, so co-mounted surfaces dedupe. */
  lastSeedIdRef: MutableRefObject<number>;
}

const ChatSessionContext = createContext<ChatSessionContextValue | null>(null);

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
  const normalized = text.replace(/\s+/g, " ").trim();
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

/**
 * Session-level home for the AI chat. The thread, the loading flag, and the
 * single send engine all live here so there is exactly ONE conversation no
 * matter how many surfaces render it — the compact dashboard rail (which App
 * mounts twice for responsive layouts) and the full-page assistant all share
 * this state. That means navigating between them, or booking + paying, keeps
 * every previous message.
 *
 * History is intentionally kept in React runtime state only — it is NOT
 * persisted, so a manual browser refresh resets the conversation to the greeting.
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
  const { events } = useCalendarEvents();
  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    { id: nextChatId(), role: "assistant", text: greeting },
  ]);
  const [loading, setLoading] = useState(false);

  const sessionIdRef = useRef<string>("");
  if (!sessionIdRef.current) {
    sessionIdRef.current =
      globalThis.crypto?.randomUUID?.() ?? `s-${Date.now()}-${Math.random().toString(36).slice(2)}`;
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

  const send = useCallback(async (text: string, opts: { mode?: ChatMode } = {}) => {
    const question = text.trim();
    if (!question || inFlight.current) return; // ignore empty + duplicate sends
    const mode = opts.mode ?? "full";

    inFlight.current = true;
    setLoading(true);
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setMessages((m) => [...m, { id: nextChatId(), role: "user", text: question }]);

    try {
      // Forward only the message + identity/session/page — the orchestrator
      // decides which agent(s) handle it (incl. travel/booking).
      const reply = await sendChatMessage(question, {
        sessionId: sessionIdRef.current,
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
      setMessages((m) => [...m, { id: nextChatId(), role: "assistant", text: msg, isError: true }]);
    } finally {
      if (abortRef.current === controller) {
        inFlight.current = false;
        setLoading(false);
        abortRef.current = null;
      }
    }
  }, [calendarContext]);

  const value = useMemo<ChatSessionContextValue>(
    () => ({ messages, loading, send, lastSeedIdRef }),
    [loading, messages, send]
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
