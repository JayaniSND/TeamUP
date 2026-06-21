export type MonthlyCalendarEventCategory =
  | "training"
  | "recovery"
  | "practice"
  | "assessment"
  | "review"
  | "rest"
  | "notes";

export interface MonthlyCalendarEvent {
  id: string;
  date: string;
  time: string;
  title: string;
  category: MonthlyCalendarEventCategory;
  status: string;
}

const EVENT_TEMPLATES: {
  day: number;
  time: string;
  title: string;
  category: MonthlyCalendarEventCategory;
  status: string;
}[] = [
  { day: 3, time: "8:00 AM", title: "Strength Training", category: "training", status: "High load" },
  { day: 5, time: "9:30 AM", title: "Recovery Session", category: "recovery", status: "Low load" },
  { day: 6, time: "4:00 PM", title: "Team Practice", category: "practice", status: "Court work" },
  { day: 8, time: "10:00 AM", title: "Mobility Check", category: "recovery", status: "Wellness" },
  { day: 10, time: "7:30 AM", title: "Sprint Assessment", category: "assessment", status: "Testing" },
  { day: 10, time: "12:30 PM", title: "Injury Prevention Notes", category: "notes", status: "Recovery signal" },
  { day: 10, time: "5:30 PM", title: "Coach Review", category: "review", status: "Feedback" },
  { day: 10, time: "6:15 PM", title: "Performance Review", category: "review", status: "Video notes" },
  { day: 14, time: "All day", title: "Rest Day", category: "rest", status: "Reset" },
  { day: 17, time: "2:00 PM", title: "Performance Review", category: "review", status: "Trend check" },
  { day: 20, time: "9:00 AM", title: "Team Practice", category: "practice", status: "Match prep" },
  { day: 21, time: "11:00 AM", title: "Coach Review", category: "review", status: "Plan update" },
  { day: 24, time: "8:30 AM", title: "Strength Training", category: "training", status: "Moderate load" },
  { day: 26, time: "9:15 AM", title: "Recovery Session", category: "recovery", status: "Low load" },
  { day: 28, time: "All day", title: "Rest Day", category: "rest", status: "Protected" },
];

const pad = (value: number) => String(value).padStart(2, "0");

const daysInMonth = (date: Date) => new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();

export const dateKey = (date: Date) =>
  `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;

export function getMockMonthlyEvents(month: Date): MonthlyCalendarEvent[] {
  const monthLength = daysInMonth(month);
  const year = month.getFullYear();
  const monthIndex = month.getMonth();

  return EVENT_TEMPLATES.filter((event) => event.day <= monthLength).map((event, index) => ({
    id: `mock-${year}-${monthIndex + 1}-${event.day}-${index}`,
    date: dateKey(new Date(year, monthIndex, event.day)),
    time: event.time,
    title: event.title,
    category: event.category,
    status: event.status,
  }));
}
