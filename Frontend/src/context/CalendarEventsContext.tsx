import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { getInitialCalendarEvents, dateKey } from "@/data/mockCalendarEvents";
import { bookingOptionKey, calendarEventBookingKey } from "@/lib/bookingIdentity";
import {
  clearPaymentSessionState,
  isPaymentSessionActive,
  restorePaymentSessionState,
  savePaymentSessionState,
} from "@/lib/paymentSessionState";
import type {
  BookingOption,
  AgentTraceEntry,
  SharedCalendarEvent,
  SharedCalendarEventType,
} from "@/types/athlete";

export interface BookingCalendarInput {
  id?: string;
  title?: string;
  startDate?: string;
  startTime?: string;
  endDate?: string;
  endTime?: string;
  type?: SharedCalendarEventType;
  bookingType?: string;
  location?: string;
  notes?: string;
  status?: string;
  source?: "booking" | "payment" | "ai-chat" | "backend";
  paymentStatus?: string;
  provider?: string;
  paymentSessionId?: string;
  bookingOptionKey?: string;
}

interface BookingConfirmation {
  event: SharedCalendarEvent;
  /** charged amount, surfaced on the success modal when known. */
  amountCents?: number;
  currency?: string;
  /** route the booking was started from, so the modal can return there. */
  returnTo?: string;
  /** backend runtime trace from payment verification/calendar preparation. */
  trace?: AgentTraceEntry[];
  flowId?: string;
  messageId?: string;
}

interface PaymentNotice {
  type: "cancelled" | "error";
  message: string;
  returnTo?: string;
}

/** A booking the user is paying for, held while the in-app checkout is open. */
interface PendingPayment {
  option: BookingOption;
  /** the route the user was on when they tapped Book & Pay. */
  originPath: string;
  bookingId?: string;
  sessionId?: string;
}

interface CalendarEventsContextValue {
  events: SharedCalendarEvent[];
  confirmation: BookingConfirmation | null;
  paymentNotice: PaymentNotice | null;
  pendingPayment: PendingPayment | null;
  addEvent: (event: SharedCalendarEvent) => SharedCalendarEvent;
  addBookingEvent: (booking: BookingCalendarInput) => SharedCalendarEvent;
  /** Open the checkout confirmation for one bookable option. */
  startPayment: (option: BookingOption) => void;
  /** Persist backend checkout identifiers before leaving for Stripe. */
  preparePaymentRedirect: (details: { bookingId?: string; sessionId?: string }) => PendingPayment | null;
  /** Mark the pending payment paid: create its calendar event + confirmation. */
  completePayment: (
    booking?: BookingCalendarInput,
    details?: {
      amountCents?: number;
      currency?: string;
      returnTo?: string;
      paymentSessionId?: string;
      trace?: AgentTraceEntry[];
      flowId?: string;
      messageId?: string;
    }
  ) => void;
  cancelPayment: (options?: { notify?: boolean; type?: "cancelled" | "error"; message?: string; returnTo?: string }) => void;
  closeConfirmation: () => void;
  closePaymentNotice: () => void;
}

const CalendarEventsContext = createContext<CalendarEventsContextValue | null>(null);

const todayKey = () => dateKey(new Date());

const currentPath = () => (typeof window !== "undefined" ? window.location.pathname : "/");

const sourcePageForPath = (path: string): "dashboard" | "chat" | "calendar" | "checkout" | "other" => {
  if (path.startsWith("/dashboard")) return "dashboard";
  if (path.startsWith("/assistant") || path.startsWith("/chat")) return "chat";
  if (path.startsWith("/calendar")) return "calendar";
  if (path.startsWith("/checkout")) return "checkout";
  return "other";
};

const loadPendingPayment = (): PendingPayment | null => {
  if (!isPaymentSessionActive()) return null;
  const restored = restorePaymentSessionState();
  const pending = restored?.pendingBooking;
  if (!pending?.option?.title || !restored?.returnRoute) return null;
  return {
    option: pending.option,
    originPath: restored.returnRoute,
    bookingId: pending.bookingId,
    sessionId: pending.stripeSessionId ?? restored.pendingPaymentSessionId,
  };
};

const loadCalendarEvents = () => {
  if (!isPaymentSessionActive()) return getInitialCalendarEvents();
  const restored = restorePaymentSessionState();
  return restored?.calendarEvents?.length ? restored.calendarEvents : getInitialCalendarEvents();
};

const paymentStart = (option: BookingOption) =>
  [option.startDate, option.startTime].filter(Boolean).join(" ");

const paymentEnd = (option: BookingOption) =>
  [option.endDate, option.endTime].filter(Boolean).join(" ");

const savePendingPayment = (pending: PendingPayment, calendarEvents: SharedCalendarEvent[]) => {
  savePaymentSessionState({
    paymentSessionId: pending.sessionId,
    calendarEvents,
    currentBookingType: pending.option.kind,
    pendingPaymentSessionId: pending.sessionId,
    returnRoute: pending.originPath,
    sourcePage: sourcePageForPath(pending.originPath),
    pageContext: pending.originPath,
    selectedCalendarDate: pending.option.startDate,
    selectedCalendarMonth: pending.option.startDate?.slice(0, 7),
    pendingBooking: {
      option: pending.option,
      type: pending.option.kind,
      title: pending.option.title,
      start: paymentStart(pending.option),
      end: paymentEnd(pending.option) || undefined,
      location: pending.option.location,
      details: pending.option.description,
      price: pending.option.amountCents,
      currency: pending.option.currency,
      stripeSessionId: pending.sessionId,
      bookingId: pending.bookingId,
    },
  });
};

const KNOWN_TYPES: SharedCalendarEventType[] = [
  "training",
  "recovery",
  "practice",
  "assessment",
  "review",
  "rest",
  "notes",
  "match",
  "travel",
  "hotel",
  "flight",
  "tournament_entry",
  "booking",
];

const eventTypeForKind = (kind?: string): SharedCalendarEventType =>
  kind && KNOWN_TYPES.includes(kind as SharedCalendarEventType)
    ? (kind as SharedCalendarEventType)
    : "booking";

const fallbackStartTime = (type?: string) => {
  if (type === "hotel") return "3:00 PM";
  if (type === "flight") return "TBD";
  return "9:00 AM";
};

function normalizeBookingEvent(booking: BookingCalendarInput): SharedCalendarEvent {
  const bookingType = booking.bookingType ?? booking.type ?? "booking";
  const eventType = booking.type ?? eventTypeForKind(String(bookingType));
  const id =
    booking.id ??
    `booking-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const startDate = booking.startDate || todayKey();
  const startTime = booking.startTime || fallbackStartTime(bookingType);
  const endDate = booking.endDate;
  const endTime = booking.endTime;
  const start = [startDate, startTime].filter(Boolean).join(" ");
  const end = [endDate, endTime].filter(Boolean).join(" ");
  const details = booking.notes;

  return {
    id,
    title: booking.title?.trim() || "Confirmed booking",
    startDate,
    startTime,
    endDate,
    endTime,
    start,
    end: end || undefined,
    type: eventType,
    location: booking.location,
    source: booking.source ?? "payment",
    notes: details,
    details,
    status: booking.status ?? "Paid",
    bookingType,
    paymentStatus: booking.paymentStatus,
    provider: booking.provider,
    createdAt: new Date().toISOString(),
    paymentSessionId: booking.paymentSessionId,
    bookingOptionKey: booking.bookingOptionKey,
  };
}

function mergeBookingInput(base: BookingCalendarInput, override?: BookingCalendarInput): BookingCalendarInput {
  if (!override) return base;
  const merged: BookingCalendarInput = { ...base };
  for (const [key, value] of Object.entries(override) as [keyof BookingCalendarInput, unknown][]) {
    if (value !== undefined && value !== "") {
      (merged as Record<string, unknown>)[key] = value;
    }
  }
  return merged;
}

export function CalendarEventsProvider({ children }: { children: ReactNode }) {
  const [events, setEvents] = useState<SharedCalendarEvent[]>(() => loadCalendarEvents());
  const [confirmation, setConfirmation] = useState<BookingConfirmation | null>(null);
  const [paymentNotice, setPaymentNotice] = useState<PaymentNotice | null>(null);
  const [pendingPayment, setPendingPayment] = useState<PendingPayment | null>(() => loadPendingPayment());

  // Append-or-replace by stable identifiers so re-confirming the same booking never duplicates.
  const upsertEvent = useCallback((event: SharedCalendarEvent) => {
    setEvents((current) => {
      const nextKey = calendarEventBookingKey(event);
      return [
        ...current.filter((item) => {
          if (item.id === event.id) return false;
          if (event.paymentSessionId && item.paymentSessionId === event.paymentSessionId) return false;
          return calendarEventBookingKey(item) !== nextKey;
        }),
        event,
      ];
    });
  }, []);

  const addEvent = useCallback(
    (event: SharedCalendarEvent) => {
      upsertEvent(event);
      return event;
    },
    [upsertEvent]
  );

  const addBookingEvent = useCallback(
    (booking: BookingCalendarInput) => {
      const event = normalizeBookingEvent({ source: "payment", ...booking });
      upsertEvent(event);
      setConfirmation({ event });
      // TODO: persist confirmed booking-created calendar events to Supabase
      // calendar_events once the product enables permanent calendar writes.
      return event;
    },
    [upsertEvent]
  );

  const startPayment = useCallback((option: BookingOption) => {
    const pending = { option, originPath: currentPath() };
    setPendingPayment(pending);
    savePendingPayment(pending, events);
  }, [events]);

  const preparePaymentRedirect = useCallback((details: { bookingId?: string; sessionId?: string }) => {
    let nextPending: PendingPayment | null = null;
    setPendingPayment((pending) => {
      if (!pending) return null;
      nextPending = { ...pending, ...details };
      savePendingPayment(nextPending, events);
      return nextPending;
    });
    return nextPending;
  }, [events]);

  const cancelPayment = useCallback((options: { notify?: boolean; type?: "cancelled" | "error"; message?: string; returnTo?: string } = {}) => {
    clearPaymentSessionState();
    setPendingPayment(null);
    if (options.notify) {
      setPaymentNotice({
        type: options.type ?? "cancelled",
        message: options.message ?? "Payment canceled. Your chat and calendar were restored.",
        returnTo: options.returnTo,
      });
    }
  }, []);

  const completePayment = useCallback((booking?: BookingCalendarInput, details?: {
    amountCents?: number;
    currency?: string;
    returnTo?: string;
    paymentSessionId?: string;
    trace?: AgentTraceEntry[];
    flowId?: string;
    messageId?: string;
  }) => {
    setPendingPayment((pending) => {
      const stored = pending ?? loadPendingPayment();
      const option = stored?.option;
      const originPath = details?.returnTo ?? stored?.originPath;
      const paymentSessionId = details?.paymentSessionId ?? stored?.sessionId ?? booking?.paymentSessionId;
      const base: BookingCalendarInput = option
        ? {
            id: stored?.bookingId ?? stored?.sessionId,
            title: option.title,
            type: eventTypeForKind(option.kind),
            bookingType: option.kind,
            startDate: option.startDate,
            startTime: option.startTime,
            endDate: option.endDate,
            endTime: option.endTime,
            location: option.location,
            notes: option.description,
            status: "Paid",
            paymentStatus: "paid",
            provider: option.provider,
            source: "payment",
            paymentSessionId,
            bookingOptionKey: bookingOptionKey(option),
          }
        : {
            status: "Paid",
            paymentStatus: "paid",
            source: "payment",
            paymentSessionId,
          };
      const event = normalizeBookingEvent(mergeBookingInput(base, booking));
      upsertEvent(event);
      setConfirmation({
        event,
        amountCents: details?.amountCents ?? option?.amountCents,
        currency: details?.currency ?? option?.currency,
        returnTo: originPath,
        trace: details?.trace,
        flowId: details?.flowId,
        messageId: details?.messageId,
      });
      clearPaymentSessionState();
      return null;
    });
  }, [upsertEvent]);

  const closeConfirmation = useCallback(() => setConfirmation(null), []);
  const closePaymentNotice = useCallback(() => setPaymentNotice(null), []);

  const value = useMemo(
    () => ({
      events,
      confirmation,
      paymentNotice,
      pendingPayment,
      addEvent,
      addBookingEvent,
      startPayment,
      preparePaymentRedirect,
      completePayment,
      cancelPayment,
      closeConfirmation,
      closePaymentNotice,
    }),
    [
      addBookingEvent,
      addEvent,
      cancelPayment,
      closeConfirmation,
      completePayment,
      confirmation,
      events,
      paymentNotice,
      pendingPayment,
      preparePaymentRedirect,
      startPayment,
    ]
  );

  return <CalendarEventsContext.Provider value={value}>{children}</CalendarEventsContext.Provider>;
}

export function useCalendarEvents() {
  const context = useContext(CalendarEventsContext);
  if (!context) {
    throw new Error("useCalendarEvents must be used inside CalendarEventsProvider");
  }
  return context;
}
