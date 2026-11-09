/** Grouping and filters for the Activity page. */

import type { EventOut, EventSource } from "#lib/api/types.ts";
import { calendarDay, clockTime, shortDate } from "#lib/format.ts";

export const ACTIVITY_PAGE = 50;

export const SOURCE_FILTERS: { value: EventSource | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "scanner", label: "Scanners" },
  { value: "ui", label: "Web app" },
  { value: "ams", label: "Printer" },
];

/** The calendar day before "2026-11-09". */
function dayBefore(day: string): string {
  const date = new Date(`${day}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() - 1);
  return date.toISOString().slice(0, 10);
}

/** "Today", "Yesterday" or "Nov 3", in the time zone in use (see setTimeZone). */
export function dayLabel(iso: string, now: Date = new Date()): string {
  const day = calendarDay(new Date(iso));
  const today = calendarDay(now);
  if (day === today) return "Today";
  if (day === dayBefore(today)) return "Yesterday";
  return shortDate(iso, now);
}

export interface Day {
  label: string;
  events: EventOut[];
}

/** Events (newest first) in runs that share a day, by when they were recorded. */
export function groupByDay(events: EventOut[], now: Date = new Date()): Day[] {
  const days: Day[] = [];
  for (const event of events) {
    const label = dayLabel(event.recorded_at, now);
    const last = days.at(-1);
    if (last?.label === label) last.events.push(event);
    else days.push({ label, events: [event] });
  }
  return days;
}

export function timeOfDay(iso: string): string {
  return clockTime(new Date(iso));
}
