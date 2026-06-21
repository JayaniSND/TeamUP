import { memo, useMemo } from "react";
import { CalendarDays, ChevronRight } from "lucide-react";
import { SectionCard } from "./SectionCard";
import { cn } from "@/lib/utils";
import type { CalendarSlotKind, WeekCalendar } from "@/types/athlete";

/** Each block kind maps to one on-palette accent (green-forward, amber for the
 *  one high-stakes tournament, neutral for travel). Color = meaning. */
const slotStyle: Record<CalendarSlotKind, string> = {
  training: "border-l-accent bg-accent/[0.08]",
  match: "border-l-ai bg-ai/[0.08]",
  recovery: "border-l-lime bg-lime/15",
  travel: "border-l-text-dim bg-surface-3",
  tournament: "border-l-warning bg-warning/10",
};

const dotStyle: Record<CalendarSlotKind, string> = {
  training: "bg-accent",
  match: "bg-ai",
  recovery: "bg-lime",
  travel: "bg-text-dim",
  tournament: "bg-warning",
};

const LEGEND: { kind: CalendarSlotKind; label: string }[] = [
  { kind: "training", label: "Training" },
  { kind: "match", label: "Match" },
  { kind: "recovery", label: "Recovery" },
];

/**
 * The weekly calendar — the dashboard's centerpiece. A full Mon→Sun grid where
 * each day carries its scheduled blocks, today is accented in green, and a
 * compact look-ahead strip points to next week's San Jose Open prep.
 */
export const WeeklyCalendar = memo(function WeeklyCalendar({
  calendar,
  onAddCalendar,
}: {
  calendar: WeekCalendar;
  onAddCalendar?: () => void;
}) {
  const counts = useMemo(() => {
    const acc: Partial<Record<CalendarSlotKind, number>> = {};
    for (const d of calendar.days) for (const s of d.slots) acc[s.kind] = (acc[s.kind] ?? 0) + 1;
    return acc;
  }, [calendar.days]);

  return (
    <SectionCard
      id="calendar"
      title="Weekly Calendar"
      subtitle={calendar.rangeLabel}
      icon={CalendarDays}
      action="Add to calendar"
      onAction={onAddCalendar}
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
          {calendar.days.map((d) => (
            <div
              key={d.day}
              className={cn(
                "flex min-h-[92px] min-w-0 flex-col rounded-2xl p-2 transition-colors",
                d.today ? "bg-accent/[0.07] ring-2 ring-accent/35" : "glass-inset"
              )}
            >
              <div className="mb-1.5 flex shrink-0 items-center justify-between">
                <span
                  className={cn(
                    "text-[10px] font-semibold uppercase tracking-wider",
                    d.today ? "text-accent" : "text-text-dim"
                  )}
                >
                  {d.day}
                </span>
                <span
                  className={cn(
                    "tnum grid size-6 place-items-center rounded-lg text-xs font-semibold",
                    d.today ? "bg-accent text-white" : "text-text"
                  )}
                >
                  {d.date}
                </span>
              </div>

              <div className="scroll-thin -mr-1 flex min-h-0 flex-1 flex-col gap-1.5 overflow-y-auto pr-1">
                {d.slots.length ? (
                  d.slots.map((s) => (
                    <div
                      key={s.id}
                      className={cn("shrink-0 rounded-lg border-l-2 px-1.5 py-1", slotStyle[s.kind])}
                    >
                      <div className="truncate text-[11px] font-semibold leading-tight text-text">{s.title}</div>
                      <div className="truncate text-[10px] text-text-dim">{s.time}</div>
                    </div>
                  ))
                ) : (
                  <div className="flex flex-1 items-center justify-center text-[10px] text-text-dim">Rest</div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* compact look-ahead — keeps the panel full without empty space */}
        <div className="mt-3 flex shrink-0 flex-wrap items-center gap-1.5 border-t border-line pt-3">
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-text-dim">
            {calendar.upcomingLabel}
            <ChevronRight className="size-3" />
          </span>
          {calendar.upcoming.map((u) => (
            <span
              key={u}
              className="glass-inset tnum rounded-full px-2.5 py-1 text-[11px] font-medium text-text-muted"
            >
              {u}
            </span>
          ))}
        </div>
      </div>
    </SectionCard>
  );
});
