import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { getInitialCalendarEvents, dateKey } from "@/data/mockCalendarEvents";
import type {
  BookingOption,
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
  source?: "booking" | "ai-chat" | "backend";
  paymentStatus?: string;
  provider?: string;
}

interface BookingConfirmation {
  event: SharedCalendarEvent;
  /** charged amount, surfaced on the success modal when known. */
  amountCents?: number;
  currency?: string;
  /** route the booking was started from, so the modal can return there. */
  returnTo?: string;
}

/** A booking the user is paying for, held while the in-app checkout is open. */
interface PendingPayment {
  option: BookingOption;
  /** the route the user was on when they tapped Book & Pay. */
  originPath: string;
}

interface CalendarEventsContextValue {
  events: SharedCalendarEvent[];
  confirmation: BookingConfirmation | null;
  pendingPayment: PendingPayment | null;
  addEvent: (event: SharedCalendarEvent) => SharedCalendarEvent;
  addBookingEvent: (booking: BookingCalendarInput) => SharedCalendarEvent;
  /** Open the in-app checkout for one bookable option (no page navigation). */
  startPayment: (option: BookingOption) => void;
  /** Mark the pending payment paid: create its calendar event + confirmation. */
  completePayment: (
    booking?: BookingCalendarInput,
    details?: { amountCents?: number; currency?: string }
  ) => void;
  cancelPayment: () => void;
  closeConfirmation: () => void;
}

const CalendarEventsContext = createContext<CalendarEventsContextValue | null>(null);

const todayKey = () => dateKey(new Date());

const currentPath = () => (typeof window !== "undefined" ? window.location.pathname : "/");

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

  return {
    id,
    title: booking.title?.trim() || "Confirmed booking",
    startDate: booking.startDate || todayKey(),
    startTime: booking.startTime || fallbackStartTime(bookingType),
    endDate: booking.endDate,
    endTime: booking.endTime,
    type: eventType,
    location: booking.location,
    source: booking.source ?? "booking",
    notes: booking.notes,
    status: booking.status ?? "Paid",
    bookingType,
    paymentStatus: booking.paymentStatus,
    provider: booking.provider,
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
  const [events, setEvents] = useState<SharedCalendarEvent[]>(() => getInitialCalendarEvents());
  const [confirmation, setConfirmation] = useState<BookingConfirmation | null>(null);
  const [pendingPayment, setPendingPayment] = useState<PendingPayment | null>(null);

  // Append-or-replace by id so re-confirming the same booking never duplicates.
  const upsertEvent = useCallback((event: SharedCalendarEvent) => {
    setEvents((current) => [...current.filter((item) => item.id !== event.id), event]);
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
      const event = normalizeBookingEvent(booking);
      upsertEvent(event);
      setConfirmation({ event });
      // TODO: persist confirmed booking-created calendar events to Supabase
      // calendar_events once the product enables permanent calendar writes.
      return event;
    },
    [upsertEvent]
  );

  // Open checkout without navigating the parent SPA. Stripe runs in a popup, so
  // chat history and route-local state survive while payment is completed.
  const startPayment = useCallback((option: BookingOption) => {
    setPendingPayment({ option, originPath: currentPath() });
  }, []);

  const cancelPayment = useCallback(() => setPendingPayment(null), []);

  const completePayment = useCallback((booking?: BookingCalendarInput, details?: { amountCents?: number; currency?: string }) => {
    setPendingPayment((pending) => {
      if (!pending) return null;
      const { option, originPath } = pending;
      const event = normalizeBookingEvent(mergeBookingInput({
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
        source: "booking",
      }, booking));
      upsertEvent(event);
      setConfirmation({
        event,
        amountCents: details?.amountCents ?? option.amountCents,
        currency: details?.currency ?? option.currency,
        returnTo: originPath,
      });
      return null;
    });
  }, [upsertEvent]);

  const closeConfirmation = useCallback(() => setConfirmation(null), []);

  const value = useMemo(
    () => ({
      events,
      confirmation,
      pendingPayment,
      addEvent,
      addBookingEvent,
      startPayment,
      completePayment,
      cancelPayment,
      closeConfirmation,
    }),
    [
      addBookingEvent,
      addEvent,
      cancelPayment,
      closeConfirmation,
      completePayment,
      confirmation,
      events,
      pendingPayment,
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
