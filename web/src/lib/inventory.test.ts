// The Inventory page's filtering, sorting and totals (lib/inventory.ts).
import { describe, expect, it } from "vitest";
import {
  activeFilters,
  ALL_TYPES,
  applyFilter,
  chosenTypes,
  filamentTypes,
  isNearlyOut,
  noFilter,
  onHand,
  savedView,
  saveView,
  shownText,
  spoolLabel,
  spoolsLink,
  statusText,
  thresholdText,
  totals,
  typeCounts,
  typeSummary,
  VIEW_KEY,
  type InventoryFilter,
} from "#lib/inventory.ts";
import { product, summary } from "../test/fixtures.ts";

function memoryStorage(): Storage {
  const data = new Map<string, string>();
  return {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => void data.set(key, value),
  } as unknown as Storage;
}

const blocked = {
  getItem: () => {
    throw new Error("blocked");
  },
  setItem: () => {
    throw new Error("blocked");
  },
} as unknown as Storage;

// Black PLA: low, 1 sealed, 1 open nearly out.
const black = summary();
// Gray PETG: 3 sealed, 2 open (one nearly out), not low.
const petg = summary({
  product: product({
    id: 2,
    display_name: "Gray PETG",
    filament_type: "PETG",
    color_rgba: "8E9089FF",
  }),
  counts: { sealed: 3, open: 2, empty: 0, unknown: 0 },
  low_stock: false,
  open_spools: [
    { id: 7, remaining_pct: null, nearly_out: false },
    { id: 8, remaining_pct: 5, nearly_out: true },
  ],
});
// White PLA: 4 sealed, none open.
const white = summary({
  product: product({ id: 3, display_name: "White PLA", color_rgba: "FFFFFFFF" }),
  counts: { sealed: 4, open: 0, empty: 1, unknown: 0 },
  low_stock: false,
  open_spools: [],
});
// ABS, all used up: not on hand.
const gone = summary({
  product: product({ id: 4, display_name: "Red ABS", filament_type: "ABS" }),
  counts: { sealed: 0, open: 0, empty: 2, unknown: 0 },
  low_stock: true,
  open_spools: [],
});
const all = [white, gone, petg, black];

function filter(changes: Partial<InventoryFilter> = {}): InventoryFilter {
  return { ...noFilter(), ...changes };
}

describe("on hand", () => {
  it("keeps products with a sealed or open spool", () => {
    expect(onHand(all)).toEqual([white, petg, black]);
  });

  it("knows a nearly-out product", () => {
    expect(isNearlyOut(petg)).toBe(true);
    expect(isNearlyOut(white)).toBe(false);
  });
});

describe("types", () => {
  it("counts the types on hand, most common first", () => {
    expect(typeCounts(all)).toEqual([
      { type: "PLA", count: 2 },
      { type: "PETG", count: 1 },
    ]);
  });

  it("breaks ties by name", () => {
    expect(typeCounts([petg, black]).map((entry) => entry.type)).toEqual(["PETG", "PLA"]);
  });

  it("treats every type picked as none picked", () => {
    expect(chosenTypes(["PLA", "PETG"], ["PLA", "PETG"])).toEqual([]);
    expect(chosenTypes(["PETG", "ABS"], ["PLA", "PETG"])).toEqual(["PETG"]);
  });

  it("names the picked types briefly", () => {
    const available = ["PLA", "PETG", "ABS", "TPU", "ASA"];
    expect(typeSummary([], available)).toBeNull();
    expect(typeSummary(["PLA", "PETG"], available)).toBe("PLA, PETG");
    expect(typeSummary(["PLA", "PETG", "TPU", "ASA"], available)).toBe("All but ABS");
    expect(typeSummary(["PLA", "PETG", "TPU"], available)).toBe("3 types");
  });

  it("lists the types for the Spools page", () => {
    expect(filamentTypes([black, petg, black])).toEqual([ALL_TYPES, "PETG", "PLA"]);
  });
});

describe("applyFilter", () => {
  it("shows every product on hand by name", () => {
    expect(applyFilter(all, noFilter())).toEqual([black, petg, white]);
  });

  it("narrows by type", () => {
    expect(applyFilter(all, filter({ types: ["PLA"] }))).toEqual([black, white]);
    expect(applyFilter(all, filter({ types: ["PLA", "PETG"] }))).toHaveLength(3);
  });

  it("narrows to low stock and nearly out", () => {
    expect(applyFilter(all, filter({ lowOnly: true }))).toEqual([black]);
    expect(applyFilter(all, filter({ nearlyOnly: true }))).toEqual([black, petg]);
  });

  it("searches the name and the hex color", () => {
    expect(applyFilter(all, filter({ query: "  gray " }))).toEqual([petg]);
    expect(applyFilter(all, filter({ query: "ffffff" }))).toEqual([white]);
    expect(applyFilter(all, filter({ query: "nothing" }))).toEqual([]);
  });

  it("sorts low first, then fewer sealed", () => {
    expect(applyFilter(all, filter({ sort: "low" }))).toEqual([black, petg, white]);
  });

  it("sorts by most stock", () => {
    const tie = summary({
      product: product({ id: 5, display_name: "Amber PLA" }),
      counts: { sealed: 4, open: 0, empty: 0, unknown: 0 },
      low_stock: false,
      open_spools: [],
    });
    expect(applyFilter([...all, tie], filter({ sort: "most" }))).toEqual([petg, tie, white, black]);
  });

  it("counts the filters that are on", () => {
    const types = ["PLA", "PETG"];
    expect(activeFilters(noFilter(), types)).toBe(0);
    expect(activeFilters(filter({ types: ["PLA", "PETG"] }), types)).toBe(0);
    expect(activeFilters(filter({ types: ["PLA"], lowOnly: true, nearlyOnly: true }), types)).toBe(
      3,
    );
    // Search and sort are not filters.
    expect(activeFilters(filter({ query: "x", sort: "low" }), types)).toBe(0);
  });
});

describe("totals", () => {
  it("adds up the products on hand", () => {
    expect(totals(all)).toEqual({ sealed: 8, open: 3, empty: 4, nearlyOut: 2, lowStock: 1 });
  });

  it("says how many are shown", () => {
    expect(shownText(11, 11)).toBe("All 11");
    expect(shownText(5, 11)).toBe("5 of 11");
  });
});

describe("text and the saved view", () => {
  it("describes thresholds and spools", () => {
    expect(thresholdText(2)).toBe("Low at 2 sealed or fewer");
    expect(thresholdText(0)).toBe("Low-stock alert off");
    expect(spoolLabel(40)).toBe("Open spool, 40 percent left");
    expect(spoolLabel(null)).toBe("Open spool, not seen by the AMS");
  });

  it("describes the status and links to the spools", () => {
    expect(statusText(black)).toBe("LOW · ≤2");
    expect(statusText(white)).toBe("OK");
    const off = summary({ low_stock: false, product: product({ low_stock_threshold: 0 }) });
    expect(statusText(off)).toBe("Alert off");
    expect(spoolsLink("Black PLA & more")).toBe("/spools?q=Black+PLA+%26+more");
  });

  it("remembers the cards or list view", () => {
    const storage = memoryStorage();
    expect(savedView(storage)).toBe("cards");
    saveView("list", storage);
    expect(storage.getItem(VIEW_KEY)).toBe("list");
    expect(savedView(storage)).toBe("list");
    expect(savedView(blocked)).toBe("cards");
    expect(() => saveView("list", blocked)).not.toThrow();
    expect(savedView()).toBe("cards");
  });
});
