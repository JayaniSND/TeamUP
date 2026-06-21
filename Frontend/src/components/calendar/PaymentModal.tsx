import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { CreditCard, Loader2, Lock, MapPin, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useCalendarEvents } from "@/context/CalendarEventsContext";
import {
  ApiError,
  createBookingCheckout,
} from "@/lib/api";
import { applyAgentTraceEvents, getAgentActivitySnapshot } from "@/lib/agents/agentActivityStore";
import { cn, formatMoney } from "@/lib/utils";

const typeLabel = (value?: string) =>
  (value || "booking").replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

/**
 * Stripe Checkout launcher. Checkout uses a same-tab redirect; the pending
 * booking is stored in session state for the Stripe round trip and cleared after
 * the return page verifies payment.
 */
export function PaymentModal() {
  const location = useLocation();
  const { pendingPayment, preparePaymentRedirect, cancelPayment } = useCalendarEvents();
  const [status, setStatus] = useState<"idle" | "creating" | "redirecting">("idle");
  const [error, setError] = useState("");

  // Reset local checkout UI whenever a new booking opens/closes.
  useEffect(() => {
    setStatus("idle");
    setError("");
  }, [pendingPayment?.option.title]);

  if (!pendingPayment || location.pathname.startsWith("/checkout/")) return null;

  const { option } = pendingPayment;
  const busy = status === "creating" || status === "redirecting";

  const pay = async () => {
    setStatus("creating");
    setError("");

    try {
      const activity = getAgentActivitySnapshot();
      const result = await createBookingCheckout(option, {
        flowId: activity.currentFlowId ?? undefined,
        messageId: activity.currentMessageId ?? undefined,
      });
      applyAgentTraceEvents(result.agentTrace);
      if (!result.ok || !result.checkoutUrl) {
        setStatus("idle");
        setError(result.error ?? "Stripe checkout could not be started.");
        return;
      }

      preparePaymentRedirect({ bookingId: result.bookingId, sessionId: result.sessionId });
      setStatus("redirecting");
      window.location.assign(result.checkoutUrl);
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
            onClick={() => cancelPayment()}
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

        {status === "redirecting" && (
          <div className="mt-3 rounded-2xl bg-accent/7 px-3 py-2 text-xs leading-relaxed text-text-muted ring-1 ring-accent/14">
            Opening Stripe Checkout in this tab. After payment, SportsMom will verify it and add the booking to your calendar.
          </div>
        )}

        {error && (
          <p className="mt-3 rounded-2xl bg-warning/10 px-3 py-2 text-xs leading-relaxed text-warning ring-1 ring-warning/20">
            {error}
          </p>
        )}

        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={() => cancelPayment()} disabled={busy}>
            Cancel
          </Button>
          <Button variant="primary" size="sm" onClick={pay} disabled={busy} className="min-w-[148px]">
            {busy ? (
              <span className="inline-flex items-center gap-1.5">
                <Loader2 className="size-3.5 animate-spin" /> {status === "redirecting" ? "Redirecting…" : "Opening…"}
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
