import { useEffect } from "react";
import { X, XCircle } from "lucide-react";
import { useCalendarEvents } from "@/context/CalendarEventsContext";

export function PaymentNoticeToast() {
  const { paymentNotice, closePaymentNotice } = useCalendarEvents();

  useEffect(() => {
    if (!paymentNotice) return;
    const id = window.setTimeout(closePaymentNotice, 4200);
    return () => window.clearTimeout(id);
  }, [closePaymentNotice, paymentNotice]);

  if (!paymentNotice) return null;
  const title = paymentNotice.type === "error" ? "Payment not confirmed" : "Payment canceled";

  return (
    <div className="fixed bottom-5 left-1/2 z-[75] w-[calc(100vw-2rem)] max-w-[420px] -translate-x-1/2">
      <div className="glass-card flex items-start gap-3 rounded-2xl p-3 shadow-[0_18px_50px_-34px_rgba(23,51,43,0.5)]">
        <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-warning/10 text-warning ring-1 ring-warning/20">
          <XCircle className="size-4.5" strokeWidth={1.9} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold text-text">{title}</div>
          <p className="mt-0.5 text-xs leading-relaxed text-text-muted">{paymentNotice.message}</p>
        </div>
        <button
          className="grid size-8 shrink-0 place-items-center rounded-xl text-text-dim transition-colors hover:bg-accent/7 hover:text-text"
          onClick={closePaymentNotice}
          aria-label="Dismiss payment notice"
        >
          <X className="size-4" />
        </button>
      </div>
    </div>
  );
}
