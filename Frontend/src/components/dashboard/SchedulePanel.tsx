import { memo } from "react";
import { CalendarDays, MapPin, Plane, Swords, Dumbbell, Trophy, Check, Circle } from "lucide-react";
import { SectionCard } from "./SectionCard";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";
import type { AthleteData, CalendarEvent } from "@/types/athlete";

const kindIcon: Record<CalendarEvent["kind"], typeof Plane> = {
  travel: Plane,
  match: Swords,
  training: Dumbbell,
  tournament: Trophy,
};

const kindColor: Record<CalendarEvent["kind"], string> = {
  travel: "text-accent bg-accent/12 ring-accent/25",
  match: "text-ai bg-ai/12 ring-ai/25",
  training: "text-positive bg-positive/12 ring-positive/25",
  tournament: "text-warning bg-warning/12 ring-warning/25",
};

export const SchedulePanel = memo(function SchedulePanel({
  schedule,
  onFindTournament,
  onAddCalendar,
}: {
  schedule: AthleteData["schedule"];
  onFindTournament: () => void;
  onAddCalendar: () => void;
}) {
  const next = schedule.events.find((e) => e.kind === "tournament") ?? schedule.events[0];

  return (
    <SectionCard
      id="schedule"
      title="Schedule & Logistics"
      subtitle="Upcoming events & travel"
      icon={CalendarDays}
      action="Find tournament"
      onAction={onFindTournament}
      delay={0.15}
    >
      {/* next event highlight */}
      <div className="grad-peach mb-4 rounded-[1.35rem] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.42)] ring-1 ring-white/45">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
            Next Event
          </span>
          <span className="tnum text-xs font-semibold text-text">{next.date}</span>
        </div>
        <div className="mt-1.5 text-base font-semibold text-text">{next.title}</div>
        <div className="mt-1 flex items-center gap-1.5 text-xs text-text-muted">
          <MapPin className="size-3.5" /> {next.location}
        </div>
      </div>

      <ul className="space-y-2">
        {schedule.events.map((e) => {
          const Icon = kindIcon[e.kind];
          return (
            <li key={e.id} className="glass-inset flex items-center gap-3 rounded-2xl px-3 py-2.5">
              <span className={cn("grid size-8 shrink-0 place-items-center rounded-lg ring-1", kindColor[e.kind])}>
                <Icon className="size-4" strokeWidth={1.75} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-text">{e.title}</div>
                <div className="text-[11px] text-text-dim">{e.location}</div>
              </div>
              <span className="tnum shrink-0 text-xs font-medium text-text-muted">{e.date}</span>
            </li>
          );
        })}
      </ul>

      {/* travel checklist */}
      <div className="glass-inset mt-4 rounded-2xl p-3">
        <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-text-muted">
          Travel checklist
        </div>
        <ul className="space-y-1.5">
          {schedule.travelChecklist.map((c) => (
            <li key={c.id} className="flex items-center gap-2 text-xs">
              {c.done ? (
                <Check className="size-3.5 text-positive" strokeWidth={2.5} />
              ) : (
                <Circle className="size-3.5 text-text-dim" strokeWidth={2} />
              )}
              <span className={cn(c.done ? "text-text-dim line-through" : "text-text-muted")}>{c.label}</span>
            </li>
          ))}
        </ul>
      </div>

      <Button variant="outline" size="sm" className="mt-3 w-full" onClick={onAddCalendar}>
        <CalendarDays className="size-3.5" />
        Add San Jose Open to calendar
      </Button>
    </SectionCard>
  );
});
