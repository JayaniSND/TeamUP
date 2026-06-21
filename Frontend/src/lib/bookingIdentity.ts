import type { BookingOption, SharedCalendarEvent } from "@/types/athlete";

const normalized = (value?: string | null) => String(value ?? "").trim().toLowerCase();

export function bookingOptionKey(option: BookingOption) {
  return [
    option.kind,
    option.title,
    option.startDate,
    option.startTime,
    option.endDate,
    option.endTime,
    option.location,
  ]
    .map(normalized)
    .join("|");
}

export function calendarEventBookingKey(event: SharedCalendarEvent) {
  return (
    event.bookingOptionKey ||
    [
      event.bookingType ?? event.type,
      event.title,
      event.startDate,
      event.startTime,
      event.endDate,
      event.endTime,
      event.location,
    ]
      .map(normalized)
      .join("|")
  );
}
