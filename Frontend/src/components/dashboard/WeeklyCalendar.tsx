import { memo, useMemo } from "react";
import { CalendarDays, ChevronRight } from "lucide-react";
import { SectionCard } from "./SectionCard";
import { dateKey, parseDateKey } from "@/data/mockCalendarEvents";
import { cn } from "@/lib/utils";
import type { SharedCalendarEvent, SharedCalendarEventType } from "@/types/athlete";

/** Each block kind maps to one on-palette accent (green-forward, amber for the
 *  one high-stakes tournament, neutral for travel). Color = meaning. */
const slotStyle: Record<SharedCalendarEventType, string> = {
  training: "border-l-accent bg-accent/[0.08]",
  recovery: "border-l-lime bg-lime/15",
  practice: "border-l-accent bg-accent/[0.08]",
  assessment: "border-l-accent bg-accent/[0.07]",
  review: "border-l-ai bg-ai/[0.08]",
  rest: "border-l-lime bg-lime/12",
  notes: "border-l-accent bg-accent/[0.06]",
  match: "border-l-ai bg-ai/[0.08]",
  travel: "border-l-text-dim bg-surface-3",
  hotel: "border-l-lime bg-lime/13",
  flight: "border-l-accent bg-accent/[0.08]",
  tournament_entry: "border-l-ai bg-ai/[0.08]",
  booking: "border-l-accent bg-accent/[0.08]",
};

const dotStyle: Record<SharedCalendarEventType, string> = {
  training: "bg-accent",
  recovery: "bg-lime",
  practice: "bg-accent",
  assessment: "bg-accent",
  review: "bg-ai",
  rest: "bg-lime",
  notes: "bg-accent",
  match: "bg-ai",
  travel: "bg-text-dim",
  hotel: "bg-lime",
  flight: "bg-accent",
  tournament_entry: "bg-ai",
  booking: "bg-accent",
};

const LEGEND: { kind: SharedCalendarEventType; label: string }[] = [
  { kind: "training", label: "Training" },
  { kind: "recovery", label: "Recovery" },
  { kind: "booking", label: "Booked" },
];

const dayLabel = new Intl.DateTimeFormat("en-US", { weekday: "short" });
const rangeLabel = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" });

function startOfWeek(date: Date) {
  const start = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const offset = (start.getDay() + 6) % 7;
  start.setDate(start.getDate() - offset);
  return start;
}

function formatRange(days: Date[]) {
  return `${rangeLabel.format(days[0])} - ${rangeLabel.format(days[days.length - 1])}`;
}

/**
 * Weekly calendar derived from the same shared event list as the month page.
 * Empty days stay empty by design; no per-week sample events are generated here.
 */
export const WeeklyCalendar = memo(function WeeklyCalendar({
  events,
  onAddCalendar,
  onOpenCalendar,
}: {
  events: SharedCalendarEvent[];
  onAddCalendar?: () => void;
  onOpenCalendar?: () => void;
}) {
  const today = useMemo(() => new Date(), []);
  const todayKey = dateKey(today);
  const focusDate = useMemo(() => {
    const upcomingMatch = events
      .filter((event) => event.type === "match" && event.startDate >= todayKey)
      .sort((a, b) => `${a.startDate} ${a.startTime}`.localeCompare(`${b.startDate} ${b.startTime}`))[0];
    return upcomingMatch ? parseDateKey(upcomingMatch.startDate) : today;
  }, [events, today, todayKey]);

  const days = useMemo(() => {
    const start = startOfWeek(focusDate);
    return Array.from({ length: 7 }, (_, index) => {
      const day = new Date(start);
      day.setDate(start.getDate() + index);
      return day;
    });
  }, [focusDate]);

  const visibleEvents = useMemo(() => {
    const start = dateKey(days[0]);
    const end = dateKey(days[days.length - 1]);
    return events
      .filter((event) => event.startDate >= start && event.startDate <= end)
      .sort((a, b) => `${a.startDate} ${a.startTime}`.localeCompare(`${b.startDate} ${b.startTime}`));
  }, [days, events]);

  const eventsByDate = useMemo(
    () =>
      visibleEvents.reduce<Record<string, SharedCalendarEvent[]>>((acc, event) => {
        acc[event.startDate] = [...(acc[event.startDate] ?? []), event];
        return acc;
      }, {}),
    [visibleEvents]
  );

  const counts = useMemo(() => {
    const acc: Partial<Record<SharedCalendarEventType, number>> = {};
    for (const event of visibleEvents) acc[event.type] = (acc[event.type] ?? 0) + 1;
    return acc;
  }, [visibleEvents]);

  return (
    <SectionCard
      id="calendar"
      title="Weekly Calendar"
      subtitle={formatRange(days)}
      icon={CalendarDays}
      action={onOpenCalendar ? "Open calendar" : "Add to calendar"}
      onAction={onOpenCalendar ?? onAddCalendar}
      onCardClick={onOpenCalendar}
      cardAriaLabel="Open monthly calendar"
      delay={0.04}
      className="h-full"
    >
      <div className="flex h-full min-h-0 flex-col">
        {/* legend / weekly summary */}
        <div className="mb-3 flex shrink-0 flex-wrap items-center gap-1.5">
          {LEGEND.map((l) => (
            <span
              key={l.kind}
              className="glass-chip inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold text-text-muted"
            >
              <span className={cn("size-1.5 rounded-full", dotStyle[l.kind])} />
              {l.label}
              <span className="tnum text-text-dim">{counts[l.kind] ?? 0}</span>
            </span>
          ))}
        </div>

        {/* 7-day grid — fills the available height so it reads as the focus */}
        <div className="grid min-h-0 flex-1 grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-7">
          {days.map((d) => {
            const key = dateKey(d);
            const dayEvents = eventsByDate[key] ?? [];
            const isToday = key === todayKey;

            return (
              <div
              key={key}
              className={cn(
                "flex min-h-[92px] min-w-0 flex-col rounded-2xl p-2 transition-colors",
                isToday ? "bg-accent/[0.07] ring-2 ring-accent/35" : "glass-inset"
              )}
            >
              <div className="mb-1.5 flex shrink-0 items-center justify-between">
                <span
                  className={cn(
                    "text-[10px] font-semibold uppercase tracking-wider",
                    isToday ? "text-accent" : "text-text-dim"
                  )}
                >
                  {dayLabel.format(d)}
                </span>
                <span
                  className={cn(
                    "tnum grid size-6 place-items-center rounded-lg text-xs font-semibold",
                    isToday ? "bg-accent text-white" : "text-text"
                  )}
                >
                  {d.getDate()}
                </span>
              </div>

              <div className="scroll-thin -mr-1 flex min-h-0 flex-1 flex-col gap-1.5 overflow-y-auto pr-1">
                {dayEvents.length ? (
                  dayEvents.map((event) => (
                    <div
                      key={event.id}
                      className={cn("shrink-0 rounded-lg border-l-2 px-1.5 py-1", slotStyle[event.type])}
                    >
                      <div className="truncate text-[11px] font-semibold leading-tight text-text">{event.title}</div>
                      <div className="truncate text-[10px] text-text-dim">
                        {event.startTime}
                        {event.location ? ` · ${event.location}` : ""}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="flex flex-1 items-center justify-center text-[10px] text-text-dim">Open</div>
                )}
              </div>
            </div>
            );
          })}
        </div>

        {/* compact source note — no fake look-ahead rows */}
        <div className="mt-3 flex shrink-0 flex-wrap items-center gap-1.5 border-t border-line pt-3">
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-text-dim">
            Shared calendar
            <ChevronRight className="size-3" />
          </span>
          <span className="glass-inset tnum rounded-full px-2.5 py-1 text-[11px] font-medium text-text-muted">
            {visibleEvents.length} event{visibleEvents.length === 1 ? "" : "s"} this week
          </span>
        </div>
      </div>
    </SectionCard>
  );
});
