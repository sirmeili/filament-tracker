import { render, screen, waitFor, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "#lib/api/client.ts";
import type { Role } from "#lib/roles.ts";
import { viewport } from "#lib/viewport.svelte.ts";
import { event, product, spoolDetail, spoolRow, summary } from "../test/fixtures.ts";

const nav = vi.hoisted(() => ({
  page: { params: { id: "1" } as Record<string, string>, url: new URL("https://localhost/") },
}));
vi.mock("$app/state", () => ({ page: nav.page }));

const stock = vi.hoisted(() => ({
  getInventory: vi.fn(),
  listSpools: vi.fn(),
  moveSpools: vi.fn(),
  getSpool: vi.fn(),
  recordAction: vi.fn(),
  undoEvent: vi.fn(),
  updateSpool: vi.fn(),
  updateProduct: vi.fn(),
}));
vi.mock("#lib/api/stock.ts", () => stock);

const { session } = await import("#lib/auth/session.svelte.ts");
const InventoryPage = (await import("./+page.svelte")).default;
const SpoolsPage = (await import("./spools/+page.svelte")).default;
const SpoolPage = (await import("./spools/[id]/+page.svelte")).default;
const ProductsPage = (await import("./products/+page.svelte")).default;

function signedInAs(role: Role): void {
  session.user = { id: 1, username: "frank", role, time_zone: "UTC" };
  session.loaded = true;
}

const BLACK = summary();
const PETG = summary({
  product: product({ id: 2, display_name: "Gray PETG", filament_type: "PETG" }),
  counts: { sealed: 3, open: 0, empty: 0, unknown: 0 },
  low_stock: false,
  open_spools: [],
});

beforeEach(() => {
  localStorage.clear();
  signedInAs("editor");
  stock.getInventory.mockResolvedValue([BLACK, PETG]);
});
afterEach(() => vi.resetAllMocks());

describe("Inventory page", () => {
  it("shows the totals and a card per product on hand", async () => {
    const gone = summary({
      product: product({ id: 3, display_name: "Red ABS", filament_type: "ABS" }),
      counts: { sealed: 0, open: 0, empty: 2, unknown: 0 },
    });
    stock.getInventory.mockResolvedValue([BLACK, PETG, gone]);
    render(InventoryPage);

    expect(await screen.findByRole("heading", { name: "Black PLA Basic" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Gray PETG" })).toBeInTheDocument();
    // Used up: not listed.
    expect(screen.queryByRole("heading", { name: "Red ABS" })).toBeNull();
    expect(screen.getByText("All 2")).toBeInTheDocument();
    expect(screen.getByText("4 sealed")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Low stock 1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Nearly out 1" })).toBeInTheDocument();
  });

  it("searches, filters, sorts and switches to a list", async () => {
    stock.getInventory.mockResolvedValue([PETG, BLACK]);
    render(InventoryPage);
    await screen.findByRole("heading", { name: "Gray PETG" });

    const names = () => screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(names()).toEqual(["Black PLA Basic", "Gray PETG"]);

    await userEvent.type(screen.getByRole("searchbox"), "gray");
    expect(names()).toEqual(["Gray PETG"]);
    expect(screen.getByText("1 of 2")).toBeInTheDocument();
    await userEvent.clear(screen.getByRole("searchbox"));

    await userEvent.click(screen.getByRole("button", { name: "Low stock 1" }));
    expect(names()).toEqual(["Black PLA Basic"]);
    await userEvent.click(screen.getByRole("button", { name: "Clear" }));

    // The sheet: PETG only, sorted by most stock.
    await userEvent.click(screen.getByRole("button", { name: "Filter" }));
    const sheet = screen.getByRole("dialog", { name: "Filter" });
    await userEvent.click(within(sheet).getByRole("button", { name: "Most stock" }));
    await userEvent.click(within(sheet).getByRole("button", { name: "Show 2 products" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(names()).toEqual(["Gray PETG", "Black PLA Basic"]);

    await userEvent.click(screen.getByRole("button", { name: "Filter" }));
    await userEvent.click(screen.getByRole("button", { name: "PETG 1" }));
    await userEvent.keyboard("{Escape}");
    expect(names()).toHaveLength(2);
    await userEvent.click(screen.getByRole("button", { name: "Filter" }));
    await userEvent.click(screen.getByRole("button", { name: "PETG 1" }));
    await userEvent.click(screen.getByRole("button", { name: "Show 1 product" }));
    expect(names()).toEqual(["Gray PETG"]);
    expect(screen.getByRole("button", { name: "PETG" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "List" }));
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("1 of 2")).toBeInTheDocument();
    expect(localStorage.getItem("ft-inventory-view")).toBe("list");
    await userEvent.click(screen.getByRole("button", { name: "Cards" }));
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("says when nothing matches and clears the filters", async () => {
    render(InventoryPage);
    await screen.findByRole("heading", { name: "Gray PETG" });

    await userEvent.type(screen.getByRole("searchbox"), "nothing like it");
    expect(screen.getByText(/No products match/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(screen.getByRole("searchbox")).toHaveValue("");
    expect(screen.getByRole("heading", { name: "Gray PETG" })).toBeInTheDocument();
  });

  it("shows the compact list on a phone, without Cards and List", async () => {
    viewport().phone = true;
    try {
      render(InventoryPage);
      const row = await screen.findByRole("button", { name: /Gray PETG/ });

      expect(screen.queryByRole("group", { name: "View" })).toBeNull();
      expect(screen.queryByRole("heading", { name: "Gray PETG" })).toBeNull();
      await userEvent.click(row);
      expect(row).toHaveAttribute("aria-expanded", "true");
      expect(screen.getByText("None open")).toBeInTheDocument();
    } finally {
      viewport().phone = false;
    }
  });

  it("says when nothing is on hand", async () => {
    stock.getInventory.mockResolvedValue([
      summary({ counts: { sealed: 0, open: 0, empty: 3, unknown: 0 }, open_spools: [] }),
    ]);
    render(InventoryPage);

    expect(await screen.findByText(/Nothing on hand/)).toBeInTheDocument();
  });

  it("says when there are no products", async () => {
    stock.getInventory.mockResolvedValue([]);
    render(InventoryPage);

    expect(await screen.findByText(/No products yet/)).toBeInTheDocument();
  });

  it("offers a retry when loading fails", async () => {
    stock.getInventory.mockRejectedValueOnce(new ApiError(0, "down"));
    render(InventoryPage);

    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server.");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "Gray PETG" })).toBeInTheDocument();
  });
});

describe("Spools page", () => {
  const page = (items = [spoolRow(), spoolRow({ id: 2, location: "Dry box" })], total = 2) => ({
    items,
    total,
    limit: 50,
    offset: 0,
  });

  it("opens searched for ?q=, from Inventory's View spools", async () => {
    nav.page.url = new URL("https://localhost/spools?q=Gray+PETG");
    try {
      stock.listSpools.mockResolvedValue(page());
      render(SpoolsPage);

      expect(await screen.findByLabelText("Search spools")).toHaveValue("Gray PETG");
      await waitFor(() =>
        expect(stock.listSpools).toHaveBeenLastCalledWith(
          expect.objectContaining({ q: "Gray PETG" }),
          expect.any(AbortSignal),
        ),
      );
    } finally {
      nav.page.url = new URL("https://localhost/");
    }
  });

  it("lists spools with counts, filters and search", async () => {
    stock.listSpools.mockResolvedValue(page());
    render(SpoolsPage);

    expect(await screen.findByText("Showing 1–2 of 2")).toBeInTheDocument();
    expect(screen.getByText("8 spools · 4 sealed · 1 open · 3 used up")).toBeInTheDocument();
    expect(stock.listSpools).toHaveBeenLastCalledWith(
      { states: [], type: undefined, q: "", limit: 50, offset: 0 },
      expect.any(AbortSignal),
    );

    await userEvent.click(screen.getByRole("button", { name: "Used up" }));
    await waitFor(() =>
      expect(stock.listSpools).toHaveBeenLastCalledWith(
        expect.objectContaining({ states: ["empty"] }),
        expect.any(AbortSignal),
      ),
    );
    await userEvent.selectOptions(screen.getByLabelText("Type"), "PETG");
    await userEvent.type(screen.getByLabelText("Search spools"), "red");
    await waitFor(() =>
      expect(stock.listSpools).toHaveBeenLastCalledWith(
        expect.objectContaining({ type: "PETG", q: "red", states: ["empty"] }),
        expect.any(AbortSignal),
      ),
    );
  });

  it("pages through results", async () => {
    stock.listSpools.mockResolvedValue(page([spoolRow()], 120));
    render(SpoolsPage);
    await screen.findByText("Showing 1–1 of 120");

    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() =>
      expect(stock.listSpools).toHaveBeenLastCalledWith(
        expect.objectContaining({ offset: 50 }),
        expect.any(AbortSignal),
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Previous" }));
    await waitFor(() =>
      expect(stock.listSpools).toHaveBeenLastCalledWith(
        expect.objectContaining({ offset: 0 }),
        expect.any(AbortSignal),
      ),
    );
  });

  it("lets editors move the selected spools", async () => {
    stock.listSpools.mockResolvedValue(page());
    stock.moveSpools.mockResolvedValue([spoolRow(), spoolRow({ id: 2 })]);
    render(SpoolsPage);
    await screen.findByText("Showing 1–2 of 2");

    await userEvent.click(screen.getByRole("checkbox", { name: "Select spool 1" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "Select spool 2" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "Select spool 2" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "Select spool 2" }));
    expect(screen.getByText("2 spools selected")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Move to"), "Shelf C");
    await userEvent.click(screen.getByRole("button", { name: "Move" }));

    expect(stock.moveSpools).toHaveBeenCalledWith([1, 2], "Shelf C");
    expect(await screen.findByRole("status")).toHaveTextContent("Moved 2 to Shelf C.");
    expect(screen.queryByText(/selected/)).toBeNull();
  });

  it("clears locations, and reports a failed move", async () => {
    stock.listSpools.mockResolvedValue(page());
    stock.moveSpools
      .mockResolvedValueOnce([spoolRow()])
      .mockRejectedValueOnce(new ApiError(403, "x"));
    render(SpoolsPage);
    await screen.findByText("Showing 1–2 of 2");

    await userEvent.click(screen.getByRole("checkbox", { name: "Select spool 1" }));
    await userEvent.click(screen.getByRole("button", { name: "Move" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Cleared the location of 1.");

    await userEvent.click(screen.getByRole("checkbox", { name: "Select spool 1" }));
    await userEvent.click(screen.getByRole("button", { name: "Move" }));
    expect(await screen.findByText("Your role cannot do that.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(screen.queryByText(/selected/)).toBeNull();
  });

  it("has no selection for viewers, and works without the counts", async () => {
    signedInAs("viewer");
    stock.getInventory.mockRejectedValue(new Error("down"));
    stock.listSpools.mockResolvedValue(page());
    render(SpoolsPage);

    await screen.findByText("Showing 1–2 of 2");
    expect(screen.queryByRole("checkbox")).toBeNull();
  });

  it("shows a load failure", async () => {
    stock.listSpools.mockRejectedValue(new ApiError(500, "boom"));
    render(SpoolsPage);

    expect(await screen.findByRole("alert")).toHaveTextContent("boom.");
  });
});

describe("Spool detail page", () => {
  beforeEach(() => {
    nav.page.params = { id: "1" };
  });

  it("shows the spool, its history and tag data", async () => {
    stock.getSpool.mockResolvedValue(spoolDetail({ placeholder: true }));
    render(SpoolPage);

    expect(await screen.findByRole("heading", { name: "Black PLA Basic" })).toBeInTheDocument();
    expect(stock.getSpool).toHaveBeenCalledWith(1);
    expect(screen.getByText(/Spool #1 · PLA · #000000/)).toBeInTheDocument();
    expect(screen.getByText("No tag yet")).toBeInTheDocument();
    expect(screen.getByText(/^Open since/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "History" })).toBeInTheDocument();
    expect(screen.getByText("GFA00")).toBeInTheDocument();
  });

  it("records an action and shows the outcome", async () => {
    stock.getSpool.mockResolvedValue(spoolDetail());
    stock.recordAction.mockResolvedValue({
      outcome: "applied",
      event: event({ type: "empty" }),
      spool: spoolDetail({ state: "empty", emptied_at: "2026-11-05T12:00:00Z" }),
    });
    render(SpoolPage);

    await userEvent.click(await screen.findByRole("button", { name: "Mark used up" }));

    expect(stock.recordAction).toHaveBeenCalledWith(1, "empty");
    expect(await screen.findByRole("status")).toHaveTextContent("Recorded.");
    expect(screen.getByRole("button", { name: "Reopen (correction)" })).toBeInTheDocument();
  });

  it("reports a refused action", async () => {
    stock.getSpool.mockResolvedValue(spoolDetail());
    stock.recordAction.mockRejectedValue(new ApiError(422, "not allowed"));
    render(SpoolPage);

    await userEvent.click(await screen.findByRole("button", { name: "Mark used up" }));

    expect(await screen.findByRole("status")).toHaveTextContent("not allowed.");
  });

  it("undoes an event and reloads", async () => {
    stock.getSpool.mockResolvedValue(spoolDetail());
    stock.undoEvent
      .mockResolvedValueOnce({})
      .mockRejectedValueOnce(new ApiError(409, "already undone"));
    render(SpoolPage);

    await userEvent.click((await screen.findAllByRole("button", { name: /^Undo Opened/ }))[0]);
    expect(stock.undoEvent).toHaveBeenCalledWith("e2");
    expect(await screen.findByText("Undid “Opened”.")).toBeInTheDocument();
    expect(stock.getSpool).toHaveBeenCalledTimes(2);

    await userEvent.click(screen.getAllByRole("button", { name: /^Undo/ })[0]);
    expect(await screen.findByText("already undone.")).toBeInTheDocument();
  });

  it("saves location and notes", async () => {
    stock.getSpool.mockResolvedValue(spoolDetail());
    stock.updateSpool.mockResolvedValue(spoolDetail({ location: "Dry box" }));
    render(SpoolPage);

    const location = await screen.findByLabelText("Location");
    await userEvent.clear(location);
    await userEvent.type(location, "Dry box");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(stock.updateSpool).toHaveBeenCalledWith(1, { location: "Dry box", notes: "Dried 8 h" });
    expect(await screen.findByText("Saved")).toBeInTheDocument();
  });

  it("is read-only for viewers", async () => {
    signedInAs("viewer");
    stock.getSpool.mockResolvedValue(spoolDetail());
    render(SpoolPage);

    await screen.findByRole("heading", { name: "Black PLA Basic" });
    expect(screen.queryByRole("button", { name: /Mark|Undo|Save/ })).toBeNull();
  });

  it("says when the spool does not exist", async () => {
    stock.getSpool.mockRejectedValue(new ApiError(404, "no such spool"));
    render(SpoolPage);

    expect(await screen.findByRole("alert")).toHaveTextContent("Not found");
  });

  it("refuses an ID that is not a number", async () => {
    nav.page.params = { id: "abc" };
    render(SpoolPage);

    expect(await screen.findByRole("alert")).toHaveTextContent("Not found");
    expect(stock.getSpool).not.toHaveBeenCalled();
  });
});

describe("Products page", () => {
  it("saves only the changed products", async () => {
    stock.updateProduct.mockResolvedValue(product());
    render(ProductsPage);

    const save = await screen.findByRole("button", { name: "Save changes" });
    expect(save).toBeDisabled();
    const [, petgPct] = screen.getAllByLabelText(/Nearly-out %/);
    await userEvent.clear(petgPct);
    await userEvent.type(petgPct, "25");
    expect(screen.getByText("1 product changed")).toBeInTheDocument();

    await userEvent.click(save);

    expect(stock.updateProduct).toHaveBeenCalledExactlyOnceWith(2, { nearly_out_pct: 25 });
    expect(await screen.findByRole("status")).toHaveTextContent("Saved");
    expect(stock.getInventory).toHaveBeenCalledTimes(2);
  });

  it("blocks saving bad values", async () => {
    render(ProductsPage);

    const [name] = await screen.findAllByLabelText(/Display name for/);
    await userEvent.clear(name);

    expect(screen.getByText("Enter a name.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  });

  it("keeps unsaved edits and says which failed", async () => {
    stock.updateProduct.mockRejectedValue(new ApiError(422, "too long"));
    render(ProductsPage);

    const [name] = await screen.findAllByLabelText(/Display name for/);
    await userEvent.type(name, " v2");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Not saved. Black PLA Basic: too long.",
    );
    expect(screen.getAllByLabelText(/Display name for/)[0]).toHaveValue("Black PLA Basic v2");
  });

  it("reports a failed reload after saving", async () => {
    stock.updateProduct.mockResolvedValue(product());
    render(ProductsPage);

    const [threshold] = await screen.findAllByLabelText(/Low-stock threshold/);
    await userEvent.type(threshold, "0");
    stock.getInventory.mockRejectedValueOnce(new ApiError(0, "down"));
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Cannot reach the server.");
  });

  it("is read-only for viewers", async () => {
    signedInAs("viewer");
    render(ProductsPage);

    const table = await screen.findByRole("table");
    expect(within(table).queryByRole("textbox")).toBeNull();
    expect(screen.queryByRole("button", { name: "Save changes" })).toBeNull();
  });

  it("says when there are no products, or loading failed", async () => {
    stock.getInventory.mockResolvedValueOnce([]);
    const { unmount } = render(ProductsPage);
    expect(await screen.findByText(/No products yet/)).toBeInTheDocument();
    unmount();

    stock.getInventory.mockRejectedValueOnce(new ApiError(0, "down"));
    render(ProductsPage);
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server.");
  });
});
