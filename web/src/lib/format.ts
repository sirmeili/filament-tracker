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

const DAY = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" });
const DAY_YEAR = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
});
const TIME = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" });

/** "Oct 12", or "Oct 12, 2025" outside the current year; "—" for none. */
export function shortDate(iso: string | null, now: Date = new Date()): string {
  if (!iso) return "—";
  const date = new Date(iso);
  return (date.getFullYear() === now.getFullYear() ? DAY : DAY_YEAR).format(date);
}

/** "4:05 PM" */
export function clockTime(at: number | Date): string {
  return TIME.format(at);
}

/** "Oct 12, 4:05 PM" */
export function dateTime(iso: string, now: Date = new Date()): string {
  return `${shortDate(iso, now)}, ${TIME.format(new Date(iso))}`;
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

/** Who recorded an event: a person in the web app, a scanner, or the admin token. */
export function eventBy(event: EventOut): string {
  if (event.username) return `${event.username} (web)`;
  if (event.device_name) return event.device_name;
  if (event.source === "ams") return "AMS";
  if (event.source === "ui") return "Admin token";
  return event.source;
}
