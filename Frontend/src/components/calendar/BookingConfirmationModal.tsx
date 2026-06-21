import { CalendarCheck2, MapPin, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/Button";
import { useCalendarEvents } from "@/context/CalendarEventsContext";
import { formatMoney } from "@/lib/utils";

const typeLabel = (value?: string) =>
  (value || "booking")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

export function BookingConfirmationModal() {
  const navigate = useNavigate();
  const { confirmation, closeConfirmation } = useCalendarEvents();

  if (!confirmation) return null;

  const { event, amountCents, currency, returnTo } = confirmation;
  const time = event.endTime ? `${event.startTime} - ${event.endTime}` : event.startTime;
  const date = event.endDate && event.endDate !== event.startDate ? `${event.startDate} - ${event.endDate}` : event.startDate;

  const viewCalendar = () => {
    closeConfirmation();
    navigate("/calendar");
  };

  // Close + return to whichever page the booking was started from. The checkout
  // return restored the temporary session first, so this route change keeps the
  // chat thread and paid calendar event in memory.
  const done = () => {
    closeConfirmation();
    if (returnTo && returnTo !== window.location.pathname) navigate(returnTo);
  };

  return (
    <div className="fixed inset-0 z-[70] grid place-items-center bg-[#17332b]/18 px-4 py-6 backdrop-blur-sm">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="booking-confirmation-title"
        className="glass-card fade-up w-full max-w-[430px] rounded-[1.65rem] p-4 shadow-[0_26px_70px_-46px_rgba(23,51,43,0.46)]"
      >
        <div className="mb-3 flex items-start gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-2xl bg-positive/12 text-positive ring-1 ring-positive/25">
            <CalendarCheck2 className="size-5" strokeWidth={1.9} />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-positive">Payment confirmed</p>
            <h2 id="booking-confirmation-title" className="mt-0.5 text-lg font-semibold tracking-tight text-text">
              Booking added to calendar
            </h2>
          </div>
          <button
            onClick={done}
            className="grid size-8 shrink-0 place-items-center rounded-xl text-text-dim transition-colors hover:bg-accent/7 hover:text-text"
            aria-label="Close confirmation"
          >
            <X className="size-4" />
          </button>
        </div>

        <div className="glass-inset rounded-2xl p-3">
          <div className="truncate text-sm font-semibold text-text">{event.title}</div>
          <div className="mt-2 grid gap-1.5 text-xs text-text-muted">
            <div className="flex justify-between gap-3">
              <span>Date</span>
              <span className="tnum font-semibold text-text">{date}</span>
            </div>
            <div className="flex justify-between gap-3">
              <span>Time</span>
              <span className="tnum font-semibold text-text">{time || "TBD"}</span>
            </div>
            <div className="flex justify-between gap-3">
              <span>Type</span>
              <span className="font-semibold text-text">{typeLabel(event.bookingType ?? event.type)}</span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span>Payment</span>
              <span className="inline-flex items-center gap-1.5 font-semibold text-positive">
                <span className="size-1.5 rounded-full bg-positive" />
                {event.status ?? "Paid"}
                {typeof amountCents === "number" && (
                  <span className="tnum text-text">· {formatMoney(amountCents, currency)}</span>
                )}
              </span>
            </div>
            {event.location && (
              <div className="flex items-center justify-between gap-3">
                <span>Location</span>
                <span className="inline-flex min-w-0 items-center gap-1 font-semibold text-text">
                  <MapPin className="size-3.5 shrink-0 text-accent" />
                  <span className="truncate">{event.location}</span>
                </span>
              </div>
            )}
            {event.provider && (
              <div className="flex justify-between gap-3">
                <span>Provider</span>
                <span className="truncate font-semibold text-text">{event.provider}</span>
              </div>
            )}
          </div>
        </div>

        {event.notes && <p className="mt-3 text-xs leading-relaxed text-text-muted">{event.notes}</p>}

        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={viewCalendar}>
            View in Calendar
          </Button>
          <Button variant="primary" size="sm" onClick={done}>
            Done
          </Button>
        </div>
      </section>
    </div>
  );
}
