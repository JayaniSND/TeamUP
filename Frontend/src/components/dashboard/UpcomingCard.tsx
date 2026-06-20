import { memo } from "react";
import { CalendarDays, Plane, Swords, Dumbbell, Trophy } from "lucide-react";
import { SectionCard } from "./SectionCard";
import { cn } from "@/lib/utils";
import type { CalendarEvent } from "@/types/athlete";

const kind: Record<CalendarEvent["kind"], { icon: typeof Plane; cls: string }> = {
  tournament: { icon: Trophy, cls: "text-warning bg-warning/12 ring-warning/25" },
  match: { icon: Swords, cls: "text-ai bg-ai/12 ring-ai/25" },
  travel: { icon: Plane, cls: "text-accent bg-accent/12 ring-accent/25" },
  training: { icon: Dumbbell, cls: "text-positive bg-positive/12 ring-positive/25" },
};

/**
 * Upcoming matches & travel — a simple, scannable list (no checklists, no
 * dense sub-cards). Like a calendar glance.
 */
export const UpcomingCard = memo(function UpcomingCard({
  events,
  onAction,
}: {
  events: CalendarEvent[];
  onAction: () => void;
}) {
  return (
    <SectionCard
      id="upcoming"
      title="Upcoming"
      subtitle="Matches & travel"
      icon={CalendarDays}
      action="Find tournament"
      onAction={onAction}
    >
      <ul className="relative space-y-2">
        <span className="absolute bottom-4 left-[1.125rem] top-4 w-px bg-gradient-to-b from-white/20 via-text/10 to-white/20" />
        {events.map((e, index) => {
          const { icon: Icon, cls } = kind[e.kind];
          return (
            <li
              key={e.id}
              className="glass-inset relative flex items-center gap-3 rounded-2xl px-3 py-3 transition-colors hover:bg-white/56"
            >
              <span className={cn("grid size-9 shrink-0 place-items-center rounded-xl ring-1", cls)}>
                <Icon className="size-4" strokeWidth={1.75} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold text-text">{e.title}</div>
                <div className="truncate text-[11px] text-text-dim">{e.location}</div>
              </div>
              <span
                className={cn(
                  "tnum shrink-0 rounded-full px-2 py-1 text-xs font-semibold",
                  index === 0 ? "bg-warning/12 text-warning ring-1 ring-warning/25" : "text-text-muted"
                )}
              >
                {e.date}
              </span>
            </li>
          );
        })}
      </ul>
    </SectionCard>
  );
});
