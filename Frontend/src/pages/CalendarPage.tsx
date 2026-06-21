import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  ArrowLeft,
  BarChart3,
  Bed,
  CalendarCheck2,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock,
  Dumbbell,
  HeartPulse,
  Hotel,
  MapPin,
  MessageSquareText,
  Plane,
  ShieldCheck,
  Trophy,
  Users,
  type LucideIcon,
} from "lucide-react";
import { Sidebar } from "@/components/dashboard/Sidebar";
import { Button } from "@/components/ui/Button";
import { athleteData } from "@/data/mockAthleteData";
import { dateKey } from "@/data/mockCalendarEvents";
import { useCalendarEvents } from "@/context/CalendarEventsContext";
import { cn } from "@/lib/utils";
import type { SharedCalendarEvent, SharedCalendarEventType } from "@/types/athlete";

const NOOP = () => {};

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const categoryMeta: Record<
  SharedCalendarEventType,
  {
    label: string;
    icon: LucideIcon;
    pill: string;
    dot: string;
  }
> = {
  training: {
    label: "Training",
    icon: Dumbbell,
    pill: "border-[#2FA084]/24 bg-[#2FA084]/10 text-[#1F6F5F]",
    dot: "bg-[#2FA084]",
  },
  recovery: {
    label: "Recovery",
    icon: HeartPulse,
    pill: "border-[#6FCF97]/36 bg-[#6FCF97]/16 text-[#1F6F5F]",
    dot: "bg-[#6FCF97]",
  },
  practice: {
    label: "Practice",
    icon: Users,
    pill: "border-[#1F6F5F]/20 bg-[#1F6F5F]/8 text-[#1F6F5F]",
    dot: "bg-[#1F6F5F]",
  },
  assessment: {
    label: "Assessment",
    icon: Activity,
    pill: "border-[#2FA084]/22 bg-[#2FA084]/8 text-[#1F6F5F]",
    dot: "bg-[#2FA084]",
  },
  review: {
    label: "Review",
    icon: BarChart3,
    pill: "border-[#1F6F5F]/18 bg-[#1F6F5F]/7 text-[#1F6F5F]",
    dot: "bg-[#1F6F5F]",
  },
  rest: {
    label: "Rest",
    icon: Bed,
    pill: "border-[#6FCF97]/30 bg-[#6FCF97]/12 text-[#1F6F5F]",
    dot: "bg-[#6FCF97]",
  },
  notes: {
    label: "Notes",
    icon: MessageSquareText,
    pill: "border-[#2FA084]/20 bg-[#2FA084]/7 text-[#1F6F5F]",
    dot: "bg-[#2FA084]",
  },
  match: {
    label: "Match",
    icon: Trophy,
    pill: "border-[#1F6F5F]/22 bg-[#1F6F5F]/8 text-[#1F6F5F]",
    dot: "bg-[#1F6F5F]",
  },
  travel: {
    label: "Travel",
    icon: Plane,
    pill: "border-[#2FA084]/22 bg-[#2FA084]/8 text-[#1F6F5F]",
    dot: "bg-[#2FA084]",
  },
  hotel: {
    label: "Hotel",
    icon: Hotel,
    pill: "border-[#6FCF97]/34 bg-[#6FCF97]/14 text-[#1F6F5F]",
    dot: "bg-[#6FCF97]",
  },
  flight: {
    label: "Flight",
    icon: Plane,
    pill: "border-[#2FA084]/22 bg-[#2FA084]/8 text-[#1F6F5F]",
    dot: "bg-[#2FA084]",
  },
  tournament_entry: {
    label: "Entry",
    icon: Trophy,
    pill: "border-[#1F6F5F]/22 bg-[#1F6F5F]/8 text-[#1F6F5F]",
    dot: "bg-[#1F6F5F]",
  },
  booking: {
    label: "Booking",
    icon: CalendarCheck2,
    pill: "border-[#2FA084]/24 bg-[#2FA084]/10 text-[#1F6F5F]",
    dot: "bg-[#2FA084]",
  },
};

const monthFormatter = new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric" });
const selectedDateFormatter = new Intl.DateTimeFormat("en-US", {
  weekday: "long",
  month: "long",
  day: "numeric",
  year: "numeric",
});
const cellDateFormatter = new Intl.DateTimeFormat("en-US", {
  weekday: "long",
  month: "long",
  day: "numeric",
});

const startOfMonth = (date: Date) => new Date(date.getFullYear(), date.getMonth(), 1);
const startOfDay = (date: Date) => new Date(date.getFullYear(), date.getMonth(), date.getDate());

function getCalendarDays(viewDate: Date) {
  const monthStart = startOfMonth(viewDate);
  const mondayOffset = (monthStart.getDay() + 6) % 7;
  const gridStart = new Date(monthStart);
  gridStart.setDate(monthStart.getDate() - mondayOffset);

  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(gridStart);
    date.setDate(gridStart.getDate() + index);
    return date;
  });
}

function groupEventsByDate(events: SharedCalendarEvent[]) {
  return events.reduce<Record<string, SharedCalendarEvent[]>>((acc, event) => {
    acc[event.startDate] = [...(acc[event.startDate] ?? []), event];
    return acc;
  }, {});
}

export default function CalendarPage() {
  const { events } = useCalendarEvents();
  const today = useMemo(() => startOfDay(new Date()), []);
  const [viewDate, setViewDate] = useState(() => startOfMonth(today));
  const [selectedDate, setSelectedDate] = useState(today);

  const eventsByDate = useMemo(() => groupEventsByDate(events), [events]);
  const calendarDays = useMemo(() => getCalendarDays(viewDate), [viewDate]);
  const selectedEvents = eventsByDate[dateKey(selectedDate)] ?? [];

  const goToMonth = (offset: number) => {
    setViewDate((current) => {
      const next = startOfMonth(new Date(current.getFullYear(), current.getMonth() + offset, 1));
      const maxDay = new Date(next.getFullYear(), next.getMonth() + 1, 0).getDate();
      const nextSelected = new Date(next.getFullYear(), next.getMonth(), Math.min(selectedDate.getDate(), maxDay));
      setSelectedDate(nextSelected);
      return next;
    });
  };

  const goToToday = () => {
    setViewDate(startOfMonth(today));
    setSelectedDate(today);
  };

  return (
    <div className="relative min-h-screen overflow-x-hidden p-3 text-text sm:p-4 lg:h-screen lg:overflow-hidden lg:p-4">
      <div className="app-aurora" />

      <div className="aurora-shell relative z-10 mx-auto flex min-h-[calc(100vh-1.5rem)] max-w-[1540px] overflow-hidden rounded-[2rem] sm:min-h-[calc(100vh-2rem)] lg:h-[calc(100vh-2rem)] lg:min-h-0">
        <Sidebar active="calendar" onSelect={NOOP} profile={athleteData.profile} />

        <div className="min-w-0 flex-1">
          <div className="sticky top-0 z-30 flex items-center gap-2 border-b border-line bg-white/85 px-4 py-2.5 backdrop-blur-md lg:hidden">
            <Link
              to="/dashboard"
              className="glass-chip grid size-8 shrink-0 place-items-center rounded-xl text-accent"
              aria-label="Back to dashboard"
            >
              <ArrowLeft className="size-4" />
            </Link>
            <span className="text-sm font-semibold text-text">Calendar</span>
          </div>

          <main className="px-3 py-4 sm:px-5 lg:h-full lg:overflow-hidden lg:px-6 lg:py-5">
            <div className="mx-auto flex h-full max-w-[1240px] flex-col">
              <header className="fade-up mb-3 flex shrink-0 flex-wrap items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-3">
                  <span className="grid size-10 shrink-0 place-items-center rounded-2xl bg-accent/12 text-accent ring-1 ring-accent/20">
                    <CalendarDays className="size-5" strokeWidth={1.9} />
                  </span>
                  <div className="min-w-0">
                    <h1 className="text-xl font-semibold tracking-tight text-text">Monthly Schedule</h1>
                    <p className="mt-0.5 text-sm text-text-muted">
                      Mock training, recovery, and review events for planning.
                    </p>
                  </div>
                </div>
                <Link to="/dashboard" className="hidden lg:block">
                  <Button variant="outline" size="sm">
                    <ArrowLeft className="size-4" strokeWidth={1.9} />
                    Dashboard
                  </Button>
                </Link>
              </header>

              <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[minmax(0,1fr)_310px]">
                <section className="glass-card fade-up flex min-h-[640px] flex-col rounded-[1.45rem] p-3.5 sm:p-4 lg:min-h-0">
                  <div className="mb-3 flex shrink-0 flex-wrap items-center justify-between gap-2">
                    <div className="min-w-0">
                      <h2 className="text-[15px] font-semibold tracking-tight text-text">{monthFormatter.format(viewDate)}</h2>
                      <p className="mt-0.5 text-[11px] text-text-dim">Monday to Sunday schedule view</p>
                    </div>

                    <div className="flex shrink-0 items-center gap-1.5">
                      <Button variant="subtle" size="icon" onClick={() => goToMonth(-1)} aria-label="Previous month">
                        <ChevronLeft className="size-4" strokeWidth={1.9} />
                      </Button>
                      <Button variant="outline" size="sm" onClick={goToToday}>
                        Today
                      </Button>
                      <Button variant="subtle" size="icon" onClick={() => goToMonth(1)} aria-label="Next month">
                        <ChevronRight className="size-4" strokeWidth={1.9} />
                      </Button>
                    </div>
                  </div>

                  <div className="scroll-thin min-h-0 flex-1 overflow-x-auto pb-1">
                    <div className="flex h-full min-w-[720px] flex-col">
                      <div className="mb-2 grid shrink-0 grid-cols-7 gap-1.5">
                        {WEEKDAYS.map((day) => (
                          <div
                            key={day}
                            className="rounded-xl bg-surface-2 px-2 py-1.5 text-center text-[10px] font-semibold uppercase tracking-wider text-text-dim ring-1 ring-line"
                          >
                            {day}
                          </div>
                        ))}
                      </div>

                      <div className="grid min-h-0 flex-1 grid-cols-7 grid-rows-6 gap-1.5">
                        {calendarDays.map((day) => {
                          const key = dateKey(day);
                          const dayEvents = eventsByDate[key] ?? [];
                          const isCurrentMonth = day.getMonth() === viewDate.getMonth();
                          const isToday = key === dateKey(today);
                          const isSelected = key === dateKey(selectedDate);
                          const visibleLimit = dayEvents.length > 3 ? 2 : 3;
                          const visibleEvents = dayEvents.slice(0, visibleLimit);
                          const hiddenCount = dayEvents.length - visibleEvents.length;

                          return (
                            <button
                              key={key}
                              type="button"
                              onClick={() => setSelectedDate(startOfDay(day))}
                              aria-current={isToday ? "date" : undefined}
                              aria-label={`${cellDateFormatter.format(day)}, ${
                                dayEvents.length === 1 ? "1 event" : `${dayEvents.length} events`
                              }`}
                              aria-pressed={isSelected}
                              className={cn(
                                "group flex min-h-[82px] min-w-0 flex-col overflow-hidden rounded-2xl border p-1 text-left transition-[background-color,border-color,box-shadow,transform] duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/35 active:translate-y-px",
                                isCurrentMonth
                                  ? "border-line bg-white hover:border-accent/25 hover:bg-[#F7FAF8]"
                                  : "border-line/60 bg-surface-2/55 text-text-dim",
                                isToday && "border-[#6FCF97]/55 bg-[#6FCF97]/10",
                                isSelected &&
                                  "border-[#2FA084]/50 bg-[#2FA084]/10 shadow-[0_0_0_1px_rgba(47,160,132,0.18),0_12px_28px_-22px_rgba(47,160,132,0.45)]"
                              )}
                            >
                              <div className="mb-0.5 flex h-5 shrink-0 items-center justify-between gap-1">
                                <span
                                  className={cn(
                                    "tnum grid size-5 place-items-center rounded-md text-[11px] font-semibold leading-none",
                                    isToday || isSelected ? "bg-[#2FA084] text-white" : "text-text",
                                    !isCurrentMonth && "text-text-dim"
                                  )}
                                >
                                  {day.getDate()}
                                </span>
                                {dayEvents.length > 0 && (
                                  <span className="tnum grid h-5 min-w-5 place-items-center rounded-full bg-[#6FCF97]/16 px-1 text-[9px] font-semibold leading-none text-[#1F6F5F]">
                                    {dayEvents.length}
                                  </span>
                                )}
                              </div>

                              <div className="flex min-h-0 flex-1 flex-col gap-px overflow-hidden">
                                {visibleEvents.map((event) => (
                                  <span
                                    key={event.id}
                                    className={cn(
                                      "calendar-event-pill flex h-[14px] max-w-full shrink-0 items-center truncate rounded-full border px-1.5 text-[9px] font-semibold leading-none",
                                      categoryMeta[event.type].pill
                                    )}
                                  >
                                    {event.title}
                                  </span>
                                ))}
                                {hiddenCount > 0 && (
                                  <span className="calendar-more-pill tnum flex h-[14px] max-w-full shrink-0 items-center truncate rounded-full bg-surface-3 px-1.5 text-[9px] font-semibold leading-none text-text-muted">
                                    +{hiddenCount} more
                                  </span>
                                )}
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                </section>

                <aside className="glass-card fade-up flex min-h-[380px] flex-col rounded-[1.45rem] p-4 lg:min-h-0">
                  <div className="mb-3 flex shrink-0 items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h2 className="text-[15px] font-semibold tracking-tight text-text">Selected Date</h2>
                      <p className="mt-0.5 text-[11px] leading-relaxed text-text-dim">
                        {selectedDateFormatter.format(selectedDate)}
                      </p>
                    </div>
                    <span className="grid size-8 shrink-0 place-items-center rounded-xl bg-accent/10 text-accent ring-1 ring-accent/18">
                      <CalendarCheck2 className="size-4" strokeWidth={1.8} />
                    </span>
                  </div>

                  <div className="mb-3 flex shrink-0 flex-wrap gap-1.5">
                    {Object.entries(categoryMeta).slice(0, 4).map(([category, meta]) => (
                      <span
                        key={category}
                        className="glass-chip inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold text-text-muted"
                      >
                        <span className={cn("size-1.5 rounded-full", meta.dot)} />
                        {meta.label}
                      </span>
                    ))}
                  </div>

                  <div className="scroll-thin min-h-0 flex-1 overflow-y-auto pr-1">
                    {selectedEvents.length ? (
                      <div className="flex flex-col gap-2">
                        {selectedEvents.map((event) => {
                          const meta = categoryMeta[event.type];
                          const Icon = meta.icon;
                          const time = event.endTime ? `${event.startTime} - ${event.endTime}` : event.startTime;
                          const dateRange =
                            event.endDate && event.endDate !== event.startDate
                              ? `${event.startDate} - ${event.endDate}`
                              : null;

                          return (
                            <div key={event.id} className="glass-inset rounded-2xl p-3">
                              <div className="mb-2 flex items-start gap-2">
                                <span className={cn("grid size-8 shrink-0 place-items-center rounded-xl border", meta.pill)}>
                                  <Icon className="size-4" strokeWidth={1.9} />
                                </span>
                                <div className="min-w-0 flex-1">
                                  <h3 className="truncate text-sm font-semibold text-text">{event.title}</h3>
                                  <div className="mt-1 flex items-center gap-1.5 text-[11px] text-text-dim">
                                    <Clock className="size-3.5" strokeWidth={1.8} />
                                    <span className="tnum">{time}</span>
                                  </div>
                                  {dateRange && (
                                    <div className="mt-1 tnum text-[11px] text-text-dim">{dateRange}</div>
                                  )}
                                  {event.location && (
                                    <div className="mt-1 flex items-center gap-1.5 text-[11px] text-text-dim">
                                      <MapPin className="size-3.5" strokeWidth={1.8} />
                                      <span className="truncate">{event.location}</span>
                                    </div>
                                  )}
                                  {event.provider && (
                                    <div className="mt-1 truncate text-[11px] font-medium text-text-dim">
                                      {event.provider}
                                    </div>
                                  )}
                                </div>
                              </div>
                              <div className="flex flex-wrap items-center gap-1.5">
                                <span className={cn("rounded-full border px-2 py-0.5 text-[10px] font-semibold", meta.pill)}>
                                  {meta.label}
                                </span>
                                <span className="rounded-full bg-surface-3 px-2 py-0.5 text-[10px] font-semibold text-text-muted">
                                  {event.status}
                                </span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="flex min-h-[220px] flex-col items-center justify-center rounded-2xl bg-surface-2 px-4 text-center ring-1 ring-line">
                        <ShieldCheck className="mb-2 size-6 text-text-dim" strokeWidth={1.8} />
                        <p className="text-sm font-semibold text-text">No events scheduled.</p>
                        <p className="mt-1 max-w-[14rem] text-xs leading-relaxed text-text-dim">
                          Pick another date to review training, recovery, and coach notes.
                        </p>
                      </div>
                    )}
                  </div>
                </aside>
              </div>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
