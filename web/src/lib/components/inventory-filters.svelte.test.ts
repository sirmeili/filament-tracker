// Inventory's search and filters, the filter sheet and the phone's compact rows.
import { render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import CompactList from "#lib/components/inventory/CompactList.svelte";
import FilterSheet from "#lib/components/inventory/FilterSheet.svelte";
import InventoryControls from "#lib/components/inventory/InventoryControls.svelte";
import { type InventoryFilter, noFilter, typeCounts } from "#lib/inventory.ts";
import { product, summary } from "../../test/fixtures.ts";

const TOTALS = { sealed: 8, open: 3, empty: 4, nearlyOut: 2, lowStock: 1 };

const black = summary();
const petg = summary({
  product: product({ id: 2, display_name: "Gray PETG", filament_type: "PETG", provisional: true }),
  counts: { sealed: 3, open: 2, empty: 0, unknown: 0 },
  low_stock: false,
  open_spools: [
    { id: 7, remaining_pct: null, nearly_out: false },
    { id: 8, remaining_pct: 40, nearly_out: false },
  ],
});
const white = summary({
  product: product({ id: 3, display_name: "White PLA", low_stock_threshold: 0 }),
  counts: { sealed: 4, open: 0, empty: 1, unknown: 0 },
  low_stock: false,
  open_spools: [],
});
const items = [black, petg, white];

/** Renders the controls with a filter whose changes are kept in `state.filter`. */
function controls(filter: InventoryFilter = noFilter(), types = ["PLA", "PETG", "ABS"]) {
  const state = $state({ filter });
  const onopen = vi.fn();
  render(InventoryControls, {
    props: {
      get filter() {
        return state.filter;
      },
      set filter(next: InventoryFilter) {
        state.filter = next;
      },
      types,
      totals: TOTALS,
      onopen,
    },
  });
  return { state, onopen };
}

describe("InventoryControls", () => {
  it("searches and toggles the quick filters", async () => {
    const { state } = controls();

    await userEvent.type(screen.getByRole("searchbox", { name: "Search name or color" }), "red");
    expect(state.filter.query).toBe("red");

    const low = screen.getByRole("button", { name: "Low stock 1" });
    await userEvent.click(low);
    expect(state.filter.lowOnly).toBe(true);
    expect(low).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "Nearly out 2" }));
    expect(state.filter.nearlyOnly).toBe(true);
    expect(screen.getByRole("button", { name: "Filter, 2 on" })).toHaveClass("on");

    // Clear keeps the search and the sort.
    await userEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(state.filter).toEqual({ ...noFilter(), query: "red" });
    expect(screen.getByRole("button", { name: "Filter" })).not.toHaveClass("on");
    expect(screen.queryByRole("button", { name: "Clear" })).toBeNull();
  });

  it("summarises the picked types, reopens the sheet and clears them", async () => {
    const { state, onopen } = controls({ ...noFilter(), types: ["PLA", "PETG"] });

    await userEvent.click(screen.getByRole("button", { name: "PLA, PETG" }));
    expect(onopen).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole("button", { name: "Filter, 1 on" }));
    expect(onopen).toHaveBeenCalledTimes(2);

    await userEvent.click(screen.getByRole("button", { name: "Clear the types" }));
    expect(state.filter.types).toEqual([]);
    expect(screen.queryByRole("button", { name: "PLA, PETG" })).toBeNull();
  });
});

describe("FilterSheet", () => {
  function sheet(filter: InventoryFilter = noFilter()) {
    const onapply = vi.fn();
    const onclose = vi.fn();
    render(FilterSheet, { items, types: typeCounts(items), filter, onapply, onclose });
    return { onapply, onclose, dialog: screen.getByRole("dialog", { name: "Filter" }) };
  }

  it("picks types, low stock and a sort, then shows the products", async () => {
    const { onapply, dialog } = sheet();

    expect(within(dialog).getByRole("button", { name: "Close" })).toHaveFocus();
    const types = within(dialog).getByRole("group", { name: "Type" });
    expect(
      within(types)
        .getAllByRole("button")
        .map((b) => b.textContent),
    ).toEqual(["PLA 2", "PETG 1"]);
    expect(within(dialog).getByRole("button", { name: "Show 3 products" })).toBeInTheDocument();

    await userEvent.click(within(types).getByRole("button", { name: "PLA 2" }));
    expect(within(dialog).getByRole("button", { name: "Show 2 products" })).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("checkbox", { name: "Low stock only" }));
    expect(within(dialog).getByRole("button", { name: "Show 1 product" })).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Most stock" }));

    await userEvent.click(within(dialog).getByRole("button", { name: "Show 1 product" }));
    expect(onapply).toHaveBeenCalledWith({
      ...noFilter(),
      types: ["PLA"],
      lowOnly: true,
      sort: "most",
    });
  });

  it("unpicks a type and clears the draft but keeps the sort", async () => {
    const { onapply, dialog } = sheet({ ...noFilter(), types: ["PETG"], sort: "low" });
    const petgChip = within(dialog).getByRole("button", { name: "PETG 1" });
    expect(petgChip).toHaveAttribute("aria-pressed", "true");

    await userEvent.click(petgChip);
    expect(petgChip).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(within(dialog).getByRole("button", { name: "PLA 2" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Clear" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Show 3 products" }));
    expect(onapply).toHaveBeenCalledWith({ ...noFilter(), sort: "low" });
  });

  it("closes with Escape, the dimmed page and Close, and keeps Tab inside", async () => {
    const { onclose, dialog } = sheet();
    const close = within(dialog).getByRole("button", { name: "Close" });
    const show = within(dialog).getByRole("button", { name: /^Show/ });

    await userEvent.tab({ shift: true });
    expect(show).toHaveFocus();
    await userEvent.tab();
    expect(close).toHaveFocus();
    await userEvent.tab();
    expect(close).not.toHaveFocus();

    await userEvent.keyboard("{Escape}");
    await userEvent.click(screen.getByRole("button", { name: "Close the filters" }));
    await userEvent.click(close);
    expect(onclose).toHaveBeenCalledTimes(3);
  });
});

describe("CompactList", () => {
  it("shows the totals and one row per product", () => {
    render(CompactList, { items, totals: TOTALS, countText: "All 3" });

    expect(screen.getByText("All 3")).toBeInTheDocument();
    const rows = screen.getAllByRole("button");
    expect(rows).toHaveLength(3);
    expect(rows[0]).toHaveTextContent("Black PLA Basic");
    expect(within(rows[0]).getByText("LOW")).toBeInTheDocument();
    expect(within(rows[0]).getByLabelText("1 sealed")).toBeInTheDocument();
    expect(within(rows[1]).queryByText("LOW")).toBeNull();
  });

  it("expands one row at a time", async () => {
    render(CompactList, { items, totals: TOTALS, countText: "All 3" });
    const [blackRow, petgRow, whiteRow] = screen.getAllByRole("button");

    await userEvent.click(blackRow);
    expect(blackRow).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("LOW · ≤2")).toBeInTheDocument();
    expect(screen.getByText("From tag")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View spools" })).toHaveAttribute(
      "href",
      "/spools?q=Black+PLA+Basic",
    );
    expect(screen.getByRole("link", { name: "Edit product" })).toHaveAttribute("href", "/products");

    await userEvent.click(petgRow);
    expect(blackRow).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText("Not seen by the AMS")).toBeInTheDocument();
    expect(screen.getByText("40%")).toBeInTheDocument();
    expect(screen.getByText("Added by hand")).toBeInTheDocument();
    expect(screen.getByText("OK")).toBeInTheDocument();

    await userEvent.click(whiteRow);
    expect(screen.getByText("None open")).toBeInTheDocument();
    expect(screen.getByText("Alert off")).toBeInTheDocument();
    expect(screen.getByText("Low-stock alert off")).toBeInTheDocument();

    await userEvent.click(whiteRow);
    expect(whiteRow).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("None open")).toBeNull();
  });
});
