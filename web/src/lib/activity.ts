/** Grouping and filters for the Activity page. */

import type { EventOut, EventSource } from "#lib/api/types.ts";
import { shortDate } from "#lib/format.ts";

export const ACTIVITY_PAGE = 50;

export const SOURCE_FILTERS: { value: EventSource | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "scanner", label: "Scanners" },
  { value: "ui", label: "Web app" },
  { value: "ams", label: "Printer" },
];

function localDay(date: Date): string {
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
}

/** "Today", "Yesterday" or "Nov 3", in the browser's time zone. */
export function dayLabel(iso: string, now: Date = new Date()): string {
  const date = new Date(iso);
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (localDay(date) === localDay(now)) return "Today";
  if (localDay(date) === localDay(yesterday)) return "Yesterday";
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

const TIME = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" });

export function timeOfDay(iso: string): string {
  return TIME.format(new Date(iso));
}
