import type { SharedCalendarEvent, SharedCalendarEventType } from "@/types/athlete";

const EVENT_TEMPLATES: {
  day: number;
  time: string;
  title: string;
  type: SharedCalendarEventType;
  status: string;
  location?: string;
  notes?: string;
}[] = [
  { day: 3, time: "8:00 AM", title: "Strength Training", type: "training", status: "High load", location: "Performance gym" },
  { day: 5, time: "9:30 AM", title: "Recovery Session", type: "recovery", status: "Low load", location: "Recovery room" },
  { day: 6, time: "4:00 PM", title: "Team Practice", type: "practice", status: "Court work", location: "Court 2" },
  { day: 8, time: "10:00 AM", title: "Mobility Check", type: "recovery", status: "Wellness", location: "Training center" },
  { day: 10, time: "7:30 AM", title: "Sprint Assessment", type: "assessment", status: "Testing", location: "Track lane 4" },
  {
    day: 10,
    time: "12:30 PM",
    title: "Injury Prevention Notes",
    type: "notes",
    status: "Recovery signal",
    notes: "Review right-knee load notes before the next high-intensity block.",
  },
  { day: 10, time: "5:30 PM", title: "Coach Review", type: "review", status: "Feedback", location: "Video room" },
  { day: 10, time: "6:15 PM", title: "Performance Review", type: "review", status: "Video notes", location: "Video room" },
  { day: 14, time: "All day", title: "Rest Day", type: "rest", status: "Reset" },
  { day: 17, time: "2:00 PM", title: "Performance Review", type: "review", status: "Trend check", location: "Video room" },
  { day: 20, time: "9:00 AM", title: "Team Practice", type: "practice", status: "Match prep", location: "Court 1" },
  { day: 21, time: "11:00 AM", title: "Coach Review", type: "review", status: "Plan update", location: "Club office" },
  { day: 24, time: "8:30 AM", title: "Strength Training", type: "training", status: "Moderate load", location: "Performance gym" },
  { day: 26, time: "9:15 AM", title: "Recovery Session", type: "recovery", status: "Low load", location: "Recovery room" },
  { day: 28, time: "All day", title: "Rest Day", type: "rest", status: "Protected" },
];

const pad = (value: number) => String(value).padStart(2, "0");

const daysInMonth = (date: Date) => new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();

export const dateKey = (date: Date) =>
  `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;

export function parseDateKey(key: string) {
  const [year, month, day] = key.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function getNextWeekThursday(baseDate = new Date()) {
  const start = new Date(baseDate.getFullYear(), baseDate.getMonth(), baseDate.getDate());
  const mondayOffset = (start.getDay() + 6) % 7;
  const nextMonday = new Date(start);
  nextMonday.setDate(start.getDate() - mondayOffset + 7);
  const nextThursday = new Date(nextMonday);
  nextThursday.setDate(nextMonday.getDate() + 3);
  return nextThursday;
}

function getInitialMatchEvent(baseDate = new Date()): SharedCalendarEvent {
  const matchDate = getNextWeekThursday(baseDate);
  return {
    id: "initial-match-next-thursday",
    title: "Match Day",
    startDate: dateKey(matchDate),
    startTime: "10:00 AM",
    endDate: dateKey(matchDate),
    endTime: "12:00 PM",
    type: "match",
    location: "TBD",
    source: "initial",
    status: "Scheduled",
    notes: "Default startup match used by the AI travel planner.",
  };
}

export function getInitialCalendarEvents(baseDate = new Date()): SharedCalendarEvent[] {
  const monthLength = daysInMonth(baseDate);
  const year = baseDate.getFullYear();
  const monthIndex = baseDate.getMonth();

  const templateEvents: SharedCalendarEvent[] = EVENT_TEMPLATES.filter((event) => event.day <= monthLength).map((event, index) => ({
    id: `initial-${year}-${monthIndex + 1}-${event.day}-${index}`,
    title: event.title,
    startDate: dateKey(new Date(year, monthIndex, event.day)),
    startTime: event.time,
    type: event.type,
    location: event.location,
    source: "initial",
    notes: event.notes,
    status: event.status,
  }));

  const matchEvent = getInitialMatchEvent(baseDate);
  return [...templateEvents.filter((event) => event.id !== matchEvent.id), matchEvent];
}
