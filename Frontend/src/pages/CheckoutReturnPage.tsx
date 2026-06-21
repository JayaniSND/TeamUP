import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useCalendarEvents, type BookingCalendarInput } from "@/context/CalendarEventsContext";
import { useChatSessionState } from "@/context/ChatSessionContext";
import {
  ApiError,
  confirmBooking,
  listBookings,
  type BookingRecord,
  type ConfirmBookingResult,
} from "@/lib/api";
import {
  hasPaymentAlreadyBeenHandled,
  markPaymentHandled,
  restorePaymentSessionState,
} from "@/lib/paymentSessionState";
import type { SharedCalendarEventType } from "@/types/athlete";

const CALENDAR_EVENT_TYPES: SharedCalendarEventType[] = [
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

const calendarTypeFrom = (value?: string): SharedCalendarEventType => {
  if (value && CALENDAR_EVENT_TYPES.includes(value as SharedCalendarEventType)) {
    return value as SharedCalendarEventType;
  }
  return "booking";
};

const bookingInputFromConfirmation = (
  result: ConfirmBookingResult,
  fetchedBooking?: BookingRecord
): BookingCalendarInput => {
  const event = result.event;
  if (event?.title || event?.startDate || event?.type) {
    return {
      id: event.id ?? result.bookingId,
      title: event.title,
      startDate: event.startDate,
      startTime: event.startTime,
      endDate: event.endDate,
      endTime: event.endTime,
      type: calendarTypeFrom(event.type ?? event.bookingType),
      bookingType: event.bookingType ?? event.type,
      location: event.location,
      notes: event.notes,
      status: "Paid",
      paymentStatus: event.paymentStatus ?? "paid",
      provider: event.provider,
      source: "payment",
    };
  }

  const booking = result.booking ?? fetchedBooking;
  if (!booking && !result.bookingId) {
    return { status: "Paid", paymentStatus: "paid", source: "payment" };
  }
  return {
    id: result.bookingId ?? booking?.id,
    title: booking?.title ?? "Confirmed booking",
    startDate: booking?.startDate,
    startTime: booking?.startTime,
    endDate: booking?.endDate,
    endTime: booking?.endTime,
    type: calendarTypeFrom(booking?.kind),
    bookingType: booking?.kind ?? "booking",
    location: booking?.location,
    notes: booking?.description,
    status: "Paid",
    paymentStatus: "paid",
    provider: booking?.provider,
    source: "payment",
  };
};

export default function CheckoutReturnPage({ status }: { status: "success" | "cancelled" }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { pendingPayment, completePayment, cancelPayment } = useCalendarEvents();
  const { appendAssistantMessage } = useChatSessionState();
  const sessionId = useMemo(() => new URLSearchParams(location.search).get("session_id"), [location.search]);
  const [state, setState] = useState<"verifying" | "done" | "cancelled" | "error">(
    status === "success" ? "verifying" : "cancelled"
  );
  const [message, setMessage] = useState("");
  const completedRunRef = useRef<string | null>(null);

  useEffect(() => {
    const runKey = `${status}:${sessionId ?? "missing"}`;
    if (completedRunRef.current === runKey) return;

    let cancelled = false;
    let returnTimer: number | undefined;
    const restoredSession = restorePaymentSessionState();
    const returnTo = pendingPayment?.originPath || restoredSession?.returnRoute || "/dashboard";
    const scheduleReturn = (delay = 0) => {
      returnTimer = window.setTimeout(() => navigate(returnTo, { replace: true }), delay);
    };

    const finish = async () => {
      if (status === "cancelled") {
        cancelPayment({ notify: true, returnTo });
        setState("cancelled");
        setMessage("Checkout cancelled. No charge was made.");
        completedRunRef.current = runKey;
        scheduleReturn(250);
        return;
      }

      if (!sessionId) {
        const msg = "Stripe returned without a session id, so no booking was added.";
        cancelPayment({ notify: true, type: "error", message: msg, returnTo });
        setState("error");
        setMessage(msg);
        completedRunRef.current = runKey;
        scheduleReturn(250);
        return;
      }

      if (hasPaymentAlreadyBeenHandled(sessionId)) {
        cancelPayment();
        setState("done");
        setMessage("Payment already confirmed. Your calendar will not be duplicated.");
        completedRunRef.current = runKey;
        scheduleReturn();
        return;
      }

      try {
        const result = await confirmBooking(sessionId);
        if (cancelled) return;
        if (!result.paid) {
          const msg = `Stripe returned ${result.status ?? "an incomplete payment"} - no booking was added.`;
          cancelPayment({ notify: true, type: "error", message: msg, returnTo });
          setState("error");
          setMessage(msg);
          completedRunRef.current = runKey;
          scheduleReturn(250);
          return;
        }

        let fetchedBooking: BookingRecord | undefined;
        if (!result.event && !result.booking && result.bookingId) {
          try {
            const bookings = await listBookings();
            fetchedBooking = bookings.find((item) => item.id === result.bookingId);
          } catch {
            // The pending checkout option still has enough detail to create one event.
          }
        }

        const bookingInput = bookingInputFromConfirmation(result, fetchedBooking);
        completePayment(bookingInput, {
          amountCents: pendingPayment?.option.amountCents,
          currency: pendingPayment?.option.currency,
          paymentSessionId: sessionId,
          returnTo,
          trace: result.agentTrace,
          flowId: result.flowId,
          messageId: result.messageId,
        });
        markPaymentHandled(sessionId);
        const bookingType = String(bookingInput.bookingType ?? bookingInput.type ?? pendingPayment?.option.kind ?? "booking")
          .replace(/_/g, " ");
        const sourcePage = restoredSession?.sourcePage ?? (returnTo.startsWith("/assistant") ? "chat" : undefined);
        if (sourcePage === "chat") {
          appendAssistantMessage(`Payment confirmed — I added your ${bookingType} to the calendar.`);
        }
        setState("done");
        setMessage("Payment confirmed. The selected booking was added to your calendar.");
        completedRunRef.current = runKey;
        scheduleReturn();
      } catch (e) {
        if (cancelled) return;
        const msg = e instanceof ApiError ? e.message : "Stripe payment was returned, but verification failed.";
        cancelPayment({
          notify: true,
          type: "error",
          message: `${msg} Your pending checkout was closed, so the booking modal will not reopen.`,
          returnTo,
        });
        setState("error");
        setMessage(msg);
        completedRunRef.current = runKey;
        scheduleReturn(250);
      }
    };

    void finish();
    return () => {
      cancelled = true;
      if (returnTimer) window.clearTimeout(returnTimer);
    };
  }, [appendAssistantMessage, cancelPayment, completePayment, navigate, pendingPayment, sessionId, status]);

  const success = state === "done";
  const failed = state === "error" || state === "cancelled";

  return (
    <div className="relative grid min-h-screen place-items-center overflow-hidden p-4 text-text">
      <div className="app-aurora" />
      <section className="glass-card relative z-10 w-full max-w-[420px] rounded-[1.7rem] p-5 text-center">
        <span className="mx-auto grid size-12 place-items-center rounded-2xl bg-accent/10 text-accent ring-1 ring-accent/18">
          {state === "verifying" ? (
            <Loader2 className="size-6 animate-spin" />
          ) : success ? (
            <CheckCircle2 className="size-6" />
          ) : (
            <XCircle className="size-6" />
          )}
        </span>
        <h1 className="mt-4 text-lg font-semibold text-text">
          {state === "verifying" ? "Verifying payment" : success ? "Payment received" : "Checkout not completed"}
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-text-muted">
          {message || "Checking Stripe and preparing your calendar update."}
        </p>
        {failed && (
          <div className="mt-4 flex justify-center">
            <Link to="/dashboard">
              <Button variant="primary" size="sm">
                Back to dashboard
              </Button>
            </Link>
          </div>
        )}
      </section>
    </div>
  );
}
