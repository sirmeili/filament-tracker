/** Helpers for the Spools and Spool detail pages. */

import type {
  ActionResult,
  ManualAction,
  ProductSummary,
  SpoolRow,
  SpoolState,
} from "#lib/api/types.ts";
import { shortDate, STATE_LABELS } from "#lib/format.ts";

export const PAGE_SIZE = 50;

export const STATE_FILTERS: { value: SpoolState | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "sealed", label: "Sealed" },
  { value: "open", label: "Open" },
  { value: "empty", label: "Used up" },
];

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

/** "34 spools · 14 sealed · 9 open · 11 used up", from the inventory counts. */
export function countText(items: ProductSummary[]): string {
  const sum = { sealed: 0, open: 0, empty: 0, unknown: 0 };
  for (const item of items) {
    sum.sealed += item.counts.sealed;
    sum.open += item.counts.open;
    sum.empty += item.counts.empty;
    sum.unknown += item.counts.unknown;
  }
  const total = sum.sealed + sum.open + sum.empty + sum.unknown;
  const parts = [
    plural(total, "spool"),
    `${sum.sealed} sealed`,
    `${sum.open} open`,
    `${sum.empty} used up`,
  ];
  if (sum.unknown) parts.push(`${sum.unknown} unknown`);
  return parts.join(" · ");
}

/** "Showing 1–13 of 34" */
export function rangeText(offset: number, shown: number, total: number): string {
  if (total === 0) return "No spools match";
  return `Showing ${offset + 1}–${offset + shown} of ${total}`;
}

/** Open, reported by the AMS, and at or below the product's nearly-out %. */
export function nearlyOut(spool: SpoolRow): boolean {
  return (
    spool.state === "open" &&
    spool.remaining_pct !== null &&
    spool.remaining_pct <= spool.product.nearly_out_pct
  );
}

/** Distinct locations, for the suggestions in the Move box. */
export function knownLocations(spools: SpoolRow[]): string[] {
  const seen = new Map<string, string>();
  for (const spool of spools) {
    const location = spool.location?.trim();
    if (location && !seen.has(location.toLowerCase())) seen.set(location.toLowerCase(), location);
  }
  return [...seen.values()].sort((a, b) => a.localeCompare(b));
}

export function selectionText(count: number): string {
  return `${plural(count, "spool")} selected`;
}

/** The line under the spool's name: "Open since Oct 20 · received Oct 12". */
export function statusLine(spool: SpoolRow, now: Date = new Date()): string {
  const received = spool.received_at ? `received ${shortDate(spool.received_at, now)}` : null;
  const opened = spool.opened_at ? `opened ${shortDate(spool.opened_at, now)}` : null;
  switch (spool.state) {
    case "open":
      return [`Open since ${shortDate(spool.opened_at, now)}`, received]
        .filter(Boolean)
        .join(" · ");
    case "empty":
      return [`Used up ${shortDate(spool.emptied_at, now)}`, opened].filter(Boolean).join(" · ");
    case "sealed":
      return received ? `Sealed, ${received}` : "Sealed";
    default:
      return "No state: every event that set it was undone";
  }
}

/** What the server did with a manual action. */
export function outcomeText(outcome: ActionResult["outcome"], state: SpoolState): string {
  if (outcome === "already_in_state")
    return `Already ${STATE_LABELS[state].toLowerCase()}; nothing changed.`;
  if (outcome === "flagged") return "Recorded, and flagged for review because it was out of order.";
  return "Recorded.";
}

export interface ActionButton {
  action: ManualAction;
  label: string;
  primary: boolean;
}

/** The manual actions offered for a state: the scanner's next step first. The server
 * applies the same rules as a scan and flags anything out of order. */
export function actionsFor(state: SpoolState): ActionButton[] {
  switch (state) {
    case "sealed":
      return [
        { action: "opened", label: "Mark opened", primary: true },
        { action: "empty", label: "Mark used up", primary: false },
      ];
    case "open":
      return [{ action: "empty", label: "Mark used up", primary: true }];
    case "empty":
      return [{ action: "opened", label: "Reopen (correction)", primary: false }];
    default:
      return [
        { action: "received", label: "Mark received", primary: true },
        { action: "opened", label: "Mark opened", primary: false },
      ];
  }
}
