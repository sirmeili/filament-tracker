/** Filtering, sorting and totals for the Inventory page. The server sends every product;
 * the page filters and sorts in the browser so the controls answer at once. */

import type { ProductSummary } from "#lib/api/types.ts";

export const ALL_TYPES = "All";

export interface Totals {
  sealed: number;
  open: number;
  nearlyOut: number;
  lowStock: number;
}

export function totals(items: ProductSummary[]): Totals {
  return items.reduce<Totals>(
    (sum, item) => ({
      sealed: sum.sealed + item.counts.sealed,
      open: sum.open + item.counts.open,
      nearlyOut: sum.nearlyOut + item.open_spools.filter((s) => s.nearly_out).length,
      lowStock: sum.lowStock + (item.low_stock ? 1 : 0),
    }),
    { sealed: 0, open: 0, nearlyOut: 0, lowStock: 0 },
  );
}

/** "All" and each filament type present, in alphabetical order. */
export function filamentTypes(items: ProductSummary[]): string[] {
  const types = new Set(items.map((item) => item.product.filament_type));
  return [ALL_TYPES, ...[...types].sort((a, b) => a.localeCompare(b))];
}

/** The products to show. The server sends them sorted by name; low stock first keeps that
 * order within each group. */
export function visibleProducts(
  items: ProductSummary[],
  type: string,
  lowFirst: boolean,
): ProductSummary[] {
  const shown = type === ALL_TYPES ? items : items.filter((i) => i.product.filament_type === type);
  return lowFirst ? [...shown].sort((a, b) => Number(b.low_stock) - Number(a.low_stock)) : shown;
}

export function thresholdText(threshold: number): string {
  return threshold > 0 ? `Low at ${threshold} sealed or fewer` : "Low-stock alert off";
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
