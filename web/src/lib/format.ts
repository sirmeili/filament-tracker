/** Display helpers shared by the pages. */

import type { EventOut, SpoolState } from "#lib/api/types.ts";

/** "#RRGGBB" from the tag's RRGGBBAA color, for the swatch; grey if it is malformed. */
export function swatchColor(rgba: string): string {
  return /^[0-9a-f]{6}/i.test(rgba) ? `#${rgba.slice(0, 6).toUpperCase()}` : "#808080";
}

/** "RRGGBB", as printed next to the swatch. */
export function hexText(rgba: string): string {
  return swatchColor(rgba).slice(1);
}

/** The UI says "Used up" for the empty state (docs/mockups/web/README.md). */
export const STATE_LABELS: Record<SpoolState, string> = {
  sealed: "Sealed",
  open: "Open",
  empty: "Used up",
  unknown: "Unknown",
};

function formatsFor(timeZone: string | undefined) {
  return {
    day: new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone }),
    dayYear: new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      timeZone,
    }),
    time: new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", timeZone }),
    // "2026-11-09": the calendar day, for comparing days.
    ymd: new Intl.DateTimeFormat("en-CA", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      timeZone,
    }),
  };
}

let zone: string | undefined;
let formats = formatsFor(undefined);

/** Show every time in the server's time zone (from the signed-in user), whatever the
 * device uses. Unset, or a name this browser does not know: the device's own. */
export function setTimeZone(timeZone: string | null | undefined): void {
  try {
    formats = formatsFor(timeZone || undefined);
    zone = timeZone || undefined;
  } catch {
    formats = formatsFor(undefined);
    zone = undefined;
  }
}

/** The time zone in use, or undefined for the device's own. */
export function currentTimeZone(): string | undefined {
  return zone;
}

/** The calendar day in the time zone in use, as "2026-11-09". */
export function calendarDay(at: number | Date): string {
  return formats.ymd.format(at);
}

/** "Oct 12", or "Oct 12, 2025" outside the current year; "—" for none. */
export function shortDate(iso: string | null, now: Date = new Date()): string {
  if (!iso) return "—";
  const date = new Date(iso);
  const sameYear = calendarDay(date).slice(0, 4) === calendarDay(now).slice(0, 4);
  return (sameYear ? formats.day : formats.dayYear).format(date);
}

/** "4:05 PM" */
export function clockTime(at: number | Date): string {
  return formats.time.format(at);
}

/** "Oct 12, 4:05 PM" */
export function dateTime(iso: string, now: Date = new Date()): string {
  return `${shortDate(iso, now)}, ${clockTime(new Date(iso))}`;
}

const EVENT_TITLES: Record<string, string> = {
  received: "Received",
  opened: "Opened",
  empty: "Used up",
  revert: "Undo",
};

export function eventTitle(type: string): string {
  return EVENT_TITLES[type] ?? type;
}

/** Who recorded an event: a person in the web app or with their own phone, a scanner, or
 * the admin token. */
export function eventBy(event: EventOut): string {
  if (event.username && event.device_name) return `${event.username} (${event.device_name})`;
  if (event.username) return `${event.username} (web)`;
  if (event.device_name) return event.device_name;
  if (event.source === "ams") return "AMS";
  if (event.source === "ui") return "Admin token";
  return event.source;
}
