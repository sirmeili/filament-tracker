/** Filtering, sorting and totals for the Inventory page. The server sends every product;
 * the page shows those on hand and filters and sorts them in the browser, so the controls
 * answer at once. */

import type { ProductSummary } from "#lib/api/types.ts";
import { hexText } from "#lib/format.ts";

export const ALL_TYPES = "All";

/** "All" and each filament type present, in alphabetical order (the Spools page's filter). */
export function filamentTypes(items: ProductSummary[]): string[] {
  const types = new Set(items.map((item) => item.product.filament_type));
  return [ALL_TYPES, ...[...types].sort((a, b) => a.localeCompare(b))];
}

/** What the Inventory page is narrowed to: search, picked types, the quick filters and the
 * sort (docs/mockups/mobile-web/). Not saved: the page opens unfiltered. */
export interface InventoryFilter {
  query: string;
  /** Picked filament types; none (or every one) means all. */
  types: string[];
  lowOnly: boolean;
  nearlyOnly: boolean;
  sort: InventorySort;
}

export type InventorySort = "name" | "low" | "most";

export const SORTS: readonly { value: InventorySort; label: string }[] = [
  { value: "low", label: "Low first" },
  { value: "name", label: "Name" },
  { value: "most", label: "Most stock" },
];

export function noFilter(): InventoryFilter {
  return { query: "", types: [], lowOnly: false, nearlyOnly: false, sort: "name" };
}

/** Products with a sealed or open spool. Used-up ones stay on Spools and Products. */
export function onHand(items: ProductSummary[]): ProductSummary[] {
  return items.filter((item) => item.counts.sealed + item.counts.open > 0);
}

/** Whether any of a product's open spools is nearly out. */
export function isNearlyOut(item: ProductSummary): boolean {
  return item.open_spools.some((spool) => spool.nearly_out);
}

/** Each filament type on hand with its product count, most common first. */
export function typeCounts(items: ProductSummary[]): { type: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const item of onHand(items)) {
    const type = item.product.filament_type;
    counts.set(type, (counts.get(type) ?? 0) + 1);
  }
  return [...counts]
    .map(([type, count]) => ({ type, count }))
    .sort((a, b) => b.count - a.count || a.type.localeCompare(b.type));
}

/** The picked types that still narrow anything: picking every type is picking none. */
export function chosenTypes(picked: string[], available: string[]): string[] {
  const chosen = available.filter((type) => picked.includes(type));
  return chosen.length === available.length ? [] : chosen;
}

/** The type chip's text, kept short: "PLA, PETG", "All but ABS" or "5 types"; null when
 * no type is picked. */
export function typeSummary(chosen: string[], available: string[]): string | null {
  if (chosen.length === 0) return null;
  if (chosen.length <= 2) return chosen.join(", ");
  const missing = available.filter((type) => !chosen.includes(type));
  return missing.length === 1 ? `All but ${missing[0]}` : `${chosen.length} types`;
}

/** How many filters are on, for the Filter button. */
export function activeFilters(filter: InventoryFilter, available: string[]): number {
  return (
    (chosenTypes(filter.types, available).length > 0 ? 1 : 0) +
    (filter.lowOnly ? 1 : 0) +
    (filter.nearlyOnly ? 1 : 0)
  );
}

function sortBy(sort: InventorySort): (a: ProductSummary, b: ProductSummary) => number {
  if (sort === "low") {
    return (a, b) =>
      Number(b.low_stock) - Number(a.low_stock) ||
      a.counts.sealed - b.counts.sealed ||
      a.product.display_name.localeCompare(b.product.display_name);
  }
  if (sort === "most") {
    return (a, b) =>
      b.counts.sealed + b.counts.open - (a.counts.sealed + a.counts.open) ||
      a.product.display_name.localeCompare(b.product.display_name);
  }
  return (a, b) => a.product.display_name.localeCompare(b.product.display_name);
}

/** The products on hand that match the filter, in its order. Search matches the name and
 * the color's hex code. */
export function applyFilter(items: ProductSummary[], filter: InventoryFilter): ProductSummary[] {
  const available = typeCounts(items).map((entry) => entry.type);
  const types = chosenTypes(filter.types, available);
  const query = filter.query.trim().toLowerCase();
  return onHand(items)
    .filter((item) => types.length === 0 || types.includes(item.product.filament_type))
    .filter((item) => !filter.lowOnly || item.low_stock)
    .filter((item) => !filter.nearlyOnly || isNearlyOut(item))
    .filter((item) => {
      if (!query) return true;
      const text = `${item.product.display_name} ${hexText(item.product.color_rgba)}`;
      return text.toLowerCase().includes(query);
    })
    .sort(sortBy(filter.sort));
}

export interface Totals {
  sealed: number;
  open: number;
  empty: number;
  /** Products with a nearly-out open spool. */
  nearlyOut: number;
  /** Products low on stock. */
  lowStock: number;
}

/** Totals over the products on hand (not just the ones shown). */
export function totals(items: ProductSummary[]): Totals {
  return onHand(items).reduce<Totals>(
    (sum, item) => ({
      sealed: sum.sealed + item.counts.sealed,
      open: sum.open + item.counts.open,
      empty: sum.empty + item.counts.empty,
      nearlyOut: sum.nearlyOut + (isNearlyOut(item) ? 1 : 0),
      lowStock: sum.lowStock + (item.low_stock ? 1 : 0),
    }),
    { sealed: 0, open: 0, empty: 0, nearlyOut: 0, lowStock: 0 },
  );
}

/** "All 11", or "5 of 11" while filtered. */
export function shownText(shown: number, all: number): string {
  return shown === all ? `All ${all}` : `${shown} of ${all}`;
}

export function thresholdText(threshold: number): string {
  return threshold > 0 ? `Low at ${threshold} sealed or fewer` : "Low-stock alert off";
}

/** "LOW · ≤2", "OK" or "Alert off". */
export function statusText(item: ProductSummary): string {
  const threshold = item.product.low_stock_threshold;
  if (item.low_stock) return `LOW · ≤${threshold}`;
  return threshold > 0 ? "OK" : "Alert off";
}

/** The Spools page searched for a product's name. */
export function spoolsLink(name: string): string {
  return `/spools?${new URLSearchParams({ q: name })}`;
}

export function spoolLabel(pct: number | null): string {
  return pct === null ? "Open spool, not seen by the AMS" : `Open spool, ${pct} percent left`;
}

export type InventoryView = "cards" | "list";
export const VIEW_KEY = "ft-inventory-view";

export function savedView(storage: Storage | undefined = globalThis.localStorage): InventoryView {
  try {
    return storage?.getItem(VIEW_KEY) === "list" ? "list" : "cards";
  } catch {
    return "cards";
  }
}

export function saveView(
  view: InventoryView,
  storage: Storage | undefined = globalThis.localStorage,
): void {
  try {
    storage?.setItem(VIEW_KEY, view);
  } catch {
    // Storage blocked: the choice lasts until the page is reloaded.
  }
}
