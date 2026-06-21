import { useCallback, useEffect, useRef, useState } from "react";
import { CreditCard, ExternalLink, Loader2, Lock, MapPin, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useCalendarEvents, type BookingCalendarInput } from "@/context/CalendarEventsContext";
import {
  ApiError,
  confirmBooking,
  createBookingCheckout,
  listBookings,
  type BookingRecord,
  type ConfirmBookingResult,
} from "@/lib/api";
import { cn, formatMoney } from "@/lib/utils";
import type { SharedCalendarEventType } from "@/types/athlete";

const typeLabel = (value?: string) =>
  (value || "booking").replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

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
      source: "booking",
    };
  }

  const booking = result.booking ?? fetchedBooking;
  if (!booking && !result.bookingId) {
    return { status: "Paid", paymentStatus: "paid", source: "booking" };
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
    source: "booking",
  };
};

type CheckoutMessage = {
  type?: string;
  status?: "success" | "cancelled";
  sessionId?: string;
};

/**
 * Stripe Checkout launcher. Stripe itself runs in a popup so the parent SPA
 * stays mounted: chat history, calendar state, and the origin route remain in
 * memory until the user manually refreshes the browser.
 */
export function PaymentModal() {
  const { pendingPayment, completePayment, cancelPayment } = useCalendarEvents();
  const [status, setStatus] = useState<"idle" | "creating" | "waiting" | "verifying">("idle");
  const [error, setError] = useState("");
  const [checkoutUrl, setCheckoutUrl] = useState<string | null>(null);
  const checkoutWindowRef = useRef<Window | null>(null);

  // Reset local checkout UI whenever a new booking opens/closes.
  useEffect(() => {
    setStatus("idle");
    setError("");
    setCheckoutUrl(null);
  }, [pendingPayment?.option.title]);

  const verifySession = useCallback(
    async (sessionId: string) => {
      setStatus("verifying");
      setError("");
      checkoutWindowRef.current?.close();

      try {
        const result = await confirmBooking(sessionId);
        if (!result.paid) {
          setStatus("idle");
          setError(`Stripe returned ${result.status ?? "an incomplete payment"} — no booking was added.`);
          return;
        }

        let fetchedBooking: BookingRecord | undefined;
        if (!result.event && !result.booking && result.bookingId) {
          try {
            const bookings = await listBookings();
            fetchedBooking = bookings.find((item) => item.id === result.bookingId);
          } catch {
            // TODO: remove this fallback once /bookings/confirm returns a full
            // structured calendar event for every paid booking.
          }
        }

        completePayment(bookingInputFromConfirmation(result, fetchedBooking));
        setStatus("idle");
      } catch (e) {
        setStatus("idle");
        setError(e instanceof ApiError ? e.message : "Stripe payment was returned, but verification failed.");
      }
    },
    [completePayment]
  );

  useEffect(() => {
    const onMessage = (event: MessageEvent<CheckoutMessage>) => {
      if (event.origin !== window.location.origin) return;
      const data = event.data;
      if (data?.type !== "teamup:stripe-checkout") return;

      if (data.status === "cancelled") {
        checkoutWindowRef.current?.close();
        setStatus("idle");
        setError("Checkout cancelled — no charge was made.");
        return;
      }

      if (data.status === "success" && data.sessionId) {
        void verifySession(data.sessionId);
      }
    };

    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [verifySession]);

  useEffect(() => {
    if (status !== "waiting") return;
    const id = window.setInterval(() => {
      if (checkoutWindowRef.current?.closed) {
        setStatus("idle");
        setError("Checkout window closed before payment confirmation.");
        window.clearInterval(id);
      }
    }, 1000);
    return () => window.clearInterval(id);
  }, [status]);

  if (!pendingPayment) return null;

  const { option } = pendingPayment;
  const busy = status === "creating" || status === "verifying";
  const waiting = status === "waiting";

  const pay = async () => {
    setStatus("creating");
    setError("");
    setCheckoutUrl(null);

    try {
      const result = await createBookingCheckout(option);
      if (!result.ok || !result.checkoutUrl) {
        setStatus("idle");
        setError(result.error ?? "Stripe checkout could not be started.");
        return;
      }

      setCheckoutUrl(result.checkoutUrl);
      const popup = window.open(
        result.checkoutUrl,
        "teamup-stripe-checkout",
        "width=520,height=760,menubar=no,toolbar=no,location=yes,status=no"
      );

      if (!popup) {
        setStatus("idle");
        setError("The browser blocked the Stripe popup. Use the secure checkout link below.");
        return;
      }

      checkoutWindowRef.current = popup;
      popup.focus();
      setStatus("waiting");
    } catch (e) {
      setStatus("idle");
      setError(e instanceof ApiError ? e.message : "Could not reach the Stripe checkout service.");
    }
  };

  return (
    <div className="fixed inset-0 z-[70] grid place-items-center bg-[#17332b]/18 px-4 py-6 backdrop-blur-sm">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="payment-modal-title"
        className="glass-card fade-up w-full max-w-[420px] rounded-[1.65rem] p-4 shadow-[0_26px_70px_-46px_rgba(23,51,43,0.46)]"
      >
        <div className="mb-3 flex items-start gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-2xl bg-accent/12 text-accent ring-1 ring-accent/25">
            <CreditCard className="size-5" strokeWidth={1.9} />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-accent">Secure checkout</p>
            <h2 id="payment-modal-title" className="mt-0.5 text-lg font-semibold tracking-tight text-text">
              Confirm your booking
            </h2>
          </div>
          <button
            onClick={cancelPayment}
            disabled={busy}
            className="grid size-8 shrink-0 place-items-center rounded-xl text-text-dim transition-colors hover:bg-accent/7 hover:text-text disabled:opacity-50"
            aria-label="Cancel checkout"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="glass-inset rounded-2xl p-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-text">{option.title}</div>
              <div className="mt-0.5 text-[11px] font-semibold uppercase tracking-wider text-text-dim">
                {typeLabel(option.kind)}
              </div>
            </div>
            <div className="tnum shrink-0 text-base font-semibold text-text">
              {formatMoney(option.amountCents, option.currency)}
            </div>
          </div>
          {option.description && (
            <p className="mt-2 text-xs leading-relaxed text-text-muted">{option.description}</p>
          )}
          {option.location && (
            <div className="mt-2 flex items-center gap-1.5 text-[11px] text-text-dim">
              <MapPin className="size-3.5 shrink-0 text-accent" />
              <span className="truncate">{option.location}</span>
            </div>
          )}
        </div>

        <div className="mt-3 flex items-center justify-between rounded-2xl bg-surface-3 px-3 py-2 text-xs">
          <span className="text-text-muted">Total due</span>
          <span className="tnum font-semibold text-text">{formatMoney(option.amountCents, option.currency)}</span>
        </div>

        {(waiting || checkoutUrl) && (
          <div className="mt-3 rounded-2xl bg-accent/7 px-3 py-2 text-xs leading-relaxed text-text-muted ring-1 ring-accent/14">
            {waiting
              ? "Stripe Checkout is open in a secure window. Complete the payment there to add this booking to your calendar."
              : "Stripe Checkout is ready. If the popup did not open, use the secure link below."}
            {checkoutUrl && !waiting && (
              <a
                href={checkoutUrl}
                target="_blank"
                rel="noreferrer"
                className="mt-2 inline-flex items-center gap-1 font-semibold text-accent hover:text-[#1F6F5F]"
              >
                Open secure Stripe checkout <ExternalLink className="size-3.5" />
              </a>
            )}
          </div>
        )}

        {error && (
          <p className="mt-3 rounded-2xl bg-warning/10 px-3 py-2 text-xs leading-relaxed text-warning ring-1 ring-warning/20">
            {error}
          </p>
        )}

        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={cancelPayment} disabled={busy}>
            Cancel
          </Button>
          <Button variant="primary" size="sm" onClick={pay} disabled={busy || waiting} className="min-w-[148px]">
            {busy ? (
              <span className="inline-flex items-center gap-1.5">
                <Loader2 className="size-3.5 animate-spin" /> {status === "verifying" ? "Verifying…" : "Opening…"}
              </span>
            ) : waiting ? (
              <span className="inline-flex items-center gap-1.5">
                <Loader2 className="size-3.5 animate-spin" /> Waiting…
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5">
                <Lock className="size-3.5" /> Pay with Stripe
              </span>
            )}
          </Button>
        </div>

        <p className={cn("mt-2 text-center text-[11px] text-text-dim")}>
          Stripe test checkout. Use test card 4242 4242 4242 4242.
        </p>
      </section>
    </div>
  );
}
