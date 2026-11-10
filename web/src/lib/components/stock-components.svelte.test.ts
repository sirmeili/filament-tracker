import { render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Header from "#lib/components/Header.svelte";
import InventoryCard from "#lib/components/inventory/InventoryCard.svelte";
import InventoryTable from "#lib/components/inventory/InventoryTable.svelte";
import SummaryTiles from "#lib/components/inventory/SummaryTiles.svelte";
import Nav from "#lib/components/Nav.svelte";
import ProductTable from "#lib/components/products/ProductTable.svelte";
import ActionCard from "#lib/components/spool/ActionCard.svelte";
import History from "#lib/components/spool/History.svelte";
import LeftOnSpool from "#lib/components/spool/LeftOnSpool.svelte";
import TagData from "#lib/components/spool/TagData.svelte";
import WhereNotes from "#lib/components/spool/WhereNotes.svelte";
import MoveBar from "#lib/components/spools/MoveBar.svelte";
import SpoolTable from "#lib/components/spools/SpoolTable.svelte";
import ThemeControl from "#lib/components/ThemeControl.svelte";
import PctBar from "#lib/components/ui/PctBar.svelte";
import Ring from "#lib/components/ui/Ring.svelte";
import StateChip from "#lib/components/ui/StateChip.svelte";
import { NAV, visibleNav } from "#lib/nav.ts";
import { draftOf } from "#lib/products.ts";
import { Theme } from "#lib/theme.svelte.ts";
import { event, product, spoolDetail, spoolRow, summary, tag } from "../../test/fixtures.ts";

function freshStorage(): Storage {
  const data = new Map<string, string>();
  return {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => void data.set(key, value),
  } as Storage;
}

describe("ui pieces", () => {
  it("draws the ring in the tag's color", () => {
    const { container } = render(Ring, { rgba: "00AE42FF", size: "sm" });

    const ring = container.querySelector(".ring") as HTMLElement;
    expect(ring.style.borderColor).toBe("rgb(0, 174, 66)");
    expect(ring).toHaveClass("sm");
    expect(ring).toHaveAttribute("aria-hidden", "true");
  });

  it("labels states", () => {
    render(StateChip, { state: "empty" });

    expect(screen.getByText("Used up")).toHaveClass("empty");
  });

  it("shows a bar, or a note when the AMS has not reported", () => {
    const { container, rerender } = render(PctBar, { pct: 9, low: true });

    expect(screen.getByText("9%")).toHaveClass("low");
    expect((container.querySelector(".bar span") as HTMLElement).style.width).toBe("9%");

    rerender({ pct: 140 });
    expect((container.querySelector(".bar span") as HTMLElement).style.width).toBe("100%");

    rerender({ pct: null });
    expect(screen.getByText("Not seen by the AMS")).toBeInTheDocument();
  });
});

describe("header", () => {
  it("links each page and marks the current one", () => {
    render(Nav, { items: visibleNav("viewer"), current: NAV[1] });

    expect(screen.getByRole("link", { name: "Spools" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Inventory" })).not.toHaveAttribute("aria-current");
  });

  it("shows the Review count only when something is waiting", () => {
    const { rerender } = render(Nav, {
      items: visibleNav("viewer"),
      current: undefined,
      badges: { "/review": 4 },
    });

    expect(screen.getByRole("link", { name: "Review, 4 waiting" })).toBeInTheDocument();
    rerender({ badges: { "/review": 0 } });
    expect(screen.getByRole("link", { name: "Review" })).toBeInTheDocument();
  });

  it("has the account button and the theme control", async () => {
    const theme = new Theme(document.createElement("html"), freshStorage(), undefined);
    render(Header, {
      user: { id: 1, username: "frank", role: "admin", time_zone: "UTC" },
      pathname: "/account",
      theme,
      reviewCount: 2,
    });

    expect(screen.getByRole("link", { name: "Roll Call" })).toHaveAttribute("href", "/");
    const account = screen.getByRole("link", { name: "frank" });
    expect(account).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Users" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Account" })).toBeNull();
    expect(screen.getByRole("link", { name: "Review, 2 waiting" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Dark theme" }));
    expect(theme.choice).toBe("dark");
    expect(screen.getByRole("button", { name: "Dark theme" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("has a Scan button only in the phone app", () => {
    const theme = new Theme(document.createElement("html"), freshStorage(), undefined);
    const props = {
      user: { id: 1, username: "frank", role: "viewer" as const, time_zone: "UTC" },
      pathname: "/",
      theme,
      reviewCount: 0,
    };
    const header = render(Header, props);
    expect(screen.queryByRole("link", { name: "Scan" })).toBeNull();

    header.rerender({ ...props, scan: true });
    expect(screen.getByRole("link", { name: "Scan" })).toHaveAttribute("href", "/scan");
  });

  it("offers light, dark and system", async () => {
    const theme = new Theme(document.createElement("html"), freshStorage(), undefined);
    render(ThemeControl, { theme });

    const group = screen.getByRole("group", { name: "Theme" });
    expect(within(group).getAllByRole("button")).toHaveLength(3);
    expect(screen.getByRole("button", { name: "Follow the device" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await userEvent.click(screen.getByRole("button", { name: "Light theme" }));
    expect(theme.choice).toBe("light");
  });
});

describe("inventory", () => {
  it("shows the totals", () => {
    render(SummaryTiles, { totals: { sealed: 14, open: 9, nearlyOut: 2, lowStock: 3 } });

    expect(screen.getByText("Open, nearly out").previousElementSibling).toHaveTextContent("2");
    expect(screen.getByText("Low on stock").previousElementSibling).toHaveTextContent("3");
  });

  it("draws a card with counts, bars and badges", () => {
    render(InventoryCard, {
      item: summary({
        product: product({ provisional: true }),
        open_spools: [
          { id: 3, remaining_pct: 12, nearly_out: true },
          { id: 4, remaining_pct: null, nearly_out: false },
        ],
      }),
    });

    expect(screen.getByRole("heading", { name: "Black PLA Basic" })).toBeInTheDocument();
    expect(screen.getByText("#000000")).toBeInTheDocument();
    expect(screen.getByText("LOW")).toBeInTheDocument();
    expect(screen.getByText("Used up").nextElementSibling).toHaveTextContent("3");
    expect(screen.getByRole("link", { name: "Open spool, 12 percent left" })).toHaveAttribute(
      "href",
      "/spools/3",
    );
    expect(
      screen.getByRole("link", { name: "Open spool, not seen by the AMS" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Low at 2 sealed or fewer")).toBeInTheDocument();
    expect(screen.getByText("Added by hand")).toBeInTheDocument();
  });

  it("leaves out the open spools section when none are open", () => {
    render(InventoryCard, { item: summary({ low_stock: false, open_spools: [] }) });

    expect(screen.queryByText("Open spools · left")).toBeNull();
    expect(screen.queryByText("LOW")).toBeNull();
  });

  it("lists the same data as a table", () => {
    render(InventoryTable, {
      items: [
        summary(),
        summary({
          product: product({
            id: 2,
            display_name: "Red",
            low_stock_threshold: 0,
            provisional: true,
          }),
          low_stock: false,
          open_spools: [],
        }),
        summary({ product: product({ id: 3, display_name: "Blue" }), low_stock: false }),
      ],
    });

    const rows = screen.getAllByRole("row");
    expect(rows).toHaveLength(4);
    expect(within(rows[1]).getByText("LOW · ≤2")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Alert off")).toBeInTheDocument();
    expect(within(rows[2]).getByText("By hand")).toBeInTheDocument();
    expect(within(rows[2]).getByText("—")).toBeInTheDocument();
    expect(within(rows[3]).getByText("OK")).toBeInTheDocument();
  });
});

describe("spools", () => {
  it("lists spools with checkboxes for editors", async () => {
    const ontoggle = vi.fn();
    render(SpoolTable, {
      spools: [
        spoolRow({ remaining_pct: 10 }),
        spoolRow({ id: 2, state: "sealed", placeholder: true, location: null, opened_at: null }),
        spoolRow({ id: 3, remaining_pct: null }),
      ],
      selected: new Set([2]),
      ontoggle,
    });

    expect(screen.getByRole("link", { name: /Black PLA Basic #1/ })).toHaveAttribute(
      "href",
      "/spools/1",
    );
    expect(screen.getByText("10%")).toHaveClass("low");
    expect(screen.getByText(/no tag yet/)).toBeInTheDocument();
    expect(screen.getByText("Not seen by the AMS")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Select spool 2" })).toBeChecked();
    await userEvent.click(screen.getByRole("checkbox", { name: "Select spool 1" }));
    expect(ontoggle).toHaveBeenCalledWith(1);
  });

  it("shows where a spool is loaded in the AMS", () => {
    const loaded = { printer_id: 1, printer_name: "P1S", ams_index: 0, tray_index: 1 };
    render(SpoolTable, {
      spools: [
        spoolRow({ id: 1, ams_slot: loaded }),
        spoolRow({ id: 2, location: null, ams_slot: loaded }),
        spoolRow({ id: 3, location: null }),
      ],
      selected: null,
    });

    const rows = screen.getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent(/Shelf A\s*AMS 1, slot 2 on P1S/);
    expect(rows[1]).toHaveTextContent("AMS 1, slot 2 on P1S");
    expect(rows[1]).not.toHaveTextContent("—AMS");
    expect(rows[2]).toHaveTextContent("—");
  });

  it("says on the spool page where it is loaded", () => {
    const slot = { printer_id: 1, printer_name: "P1S", ams_index: 0, tray_index: 3 };
    render(WhereNotes, { spool: spoolDetail({ ams_slot: slot }), canEdit: false, onsave: vi.fn() });

    expect(screen.getByText("Loaded in AMS 1, slot 4 on P1S")).toBeInTheDocument();
  });

  it("follows the spool when another one is shown", async () => {
    const slot = { printer_id: 1, printer_name: "P1S", ams_index: 0, tray_index: 0 };
    const { rerender } = render(WhereNotes, {
      spool: spoolDetail({ location: null, notes: null }),
      canEdit: true,
      onsave: vi.fn(),
    });
    expect(screen.getByLabelText("Location")).toHaveValue("");
    expect(screen.queryByText(/Loaded in/)).toBeNull();

    await rerender({
      spool: spoolDetail({ id: 2, location: "Dry box", notes: "x", ams_slot: slot }),
    });

    expect(screen.getByLabelText("Location")).toHaveValue("Dry box");
    expect(screen.getByLabelText("Notes")).toHaveValue("x");
    expect(screen.getByText("Loaded in AMS 1, slot 1 on P1S")).toBeInTheDocument();

    await rerender({ spool: spoolDetail({ id: 3, location: null }), canEdit: false });
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("updates rows when the spools change", async () => {
    const slot = { printer_id: 1, printer_name: "P1S", ams_index: 0, tray_index: 0 };
    const { rerender } = render(SpoolTable, {
      spools: [spoolRow({ location: null })],
      selected: new Set<number>(),
      ontoggle: vi.fn(),
    });
    expect(screen.getByRole("row", { name: /Black PLA/ })).toHaveTextContent("—");

    await rerender({
      spools: [spoolRow({ location: "Shelf B", placeholder: true, ams_slot: slot })],
      selected: new Set([1]),
    });

    const row = screen.getAllByRole("row")[1];
    expect(row).toHaveTextContent(/Shelf B\s*AMS 1, slot 1 on P1S/);
    expect(row).toHaveTextContent(/no tag yet/);
    expect(within(row).getByRole("checkbox")).toBeChecked();
  });

  it("has no checkboxes for viewers", () => {
    render(SpoolTable, { spools: [spoolRow()], selected: null });

    expect(screen.queryByRole("checkbox")).toBeNull();
  });

  it("moves the selection to a typed location, or clears it", async () => {
    const onmove = vi.fn();
    const onclear = vi.fn();
    render(MoveBar, { count: 2, locations: ["Dry box"], busy: false, onmove, onclear });

    expect(screen.getByText("2 spools selected")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Move" }));
    expect(onmove).toHaveBeenLastCalledWith(null);
    await userEvent.type(screen.getByLabelText("Move to"), " Shelf C ");
    await userEvent.click(screen.getByRole("button", { name: "Move" }));
    expect(onmove).toHaveBeenLastCalledWith("Shelf C");
    await userEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(onclear).toHaveBeenCalledOnce();
  });
});

describe("spool detail", () => {
  it("offers the actions for the state", async () => {
    const onaction = vi.fn();
    render(ActionCard, { state: "sealed", busy: false, message: "Recorded.", onaction });

    expect(screen.getByRole("status")).toHaveTextContent("Recorded.");
    await userEvent.click(screen.getByRole("button", { name: "Mark opened" }));
    expect(onaction).toHaveBeenCalledWith("opened");
  });

  it("shows the history with undo and undone events struck through", async () => {
    const onundo = vi.fn();
    const opened = event({
      id: "e2",
      type: "opened",
      reverted_by: "e3",
      can_undo: false,
      flagged: true,
    });
    render(History, {
      props: {
        events: [
          event({ id: "e3", type: "revert", reverts: "e2", username: "frank", can_undo: false }),
          event({ id: "e4", type: "revert", reverts: "gone", can_undo: false }),
          opened,
          event(),
        ],
        canUndo: true,
        busy: false,
        onundo,
      },
    });

    expect(screen.getByText("Undid “Opened”")).toBeInTheDocument();
    expect(screen.getByText("Undo", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByText("Opened")).toHaveClass("struck");
    expect(screen.getByText("Flagged")).toBeInTheDocument();
    expect(screen.getByText(/frank \(web\)/)).toBeInTheDocument();
    const undo = screen.getAllByRole("button", { name: /^Undo Received/ });
    expect(undo).toHaveLength(1);
    await userEvent.click(undo[0]);
    expect(onundo).toHaveBeenCalledWith(expect.objectContaining({ id: "e1" }));
  });

  it("hides undo from viewers and says when there are no events", () => {
    const { rerender } = render(History, {
      props: { events: [event()], canUndo: false, busy: false, onundo: vi.fn() },
    });
    expect(screen.queryByRole("button")).toBeNull();
    rerender({ events: [] });
    expect(screen.getByText("No events.")).toBeInTheDocument();
  });

  it("shows what is left, and grams when the weight is known", () => {
    const { rerender } = render(LeftOnSpool, { spool: spoolDetail({ remaining_pct: 62 }) });
    expect(screen.getByText("62%")).toBeInTheDocument();
    expect(screen.getByText("about 620 g of 1000 g")).toBeInTheDocument();

    rerender({ spool: spoolDetail({ remaining_pct: 12, grams_left: null }) });
    expect(screen.getByText(/Nearly out \(at or below 15%\)/)).toBeInTheDocument();
    expect(screen.queryByText(/about/)).toBeNull();

    rerender({ spool: spoolDetail({ remaining_pct: null, grams_left: null }) });
    expect(screen.getByText(/Not seen by the AMS yet/)).toBeInTheDocument();
    expect(screen.getByText("Full spool: 1000 g")).toBeInTheDocument();

    rerender({ spool: spoolDetail({ remaining_pct: null, spool_weight_g: null }) });
    expect(screen.queryByText(/Full spool/)).toBeNull();
  });

  it("saves location and notes", async () => {
    const onsave = vi.fn().mockResolvedValue(undefined);
    render(WhereNotes, { spool: spoolDetail(), canEdit: true, onsave });

    const save = screen.getByRole("button", { name: "Save" });
    expect(save).toBeDisabled();
    await userEvent.clear(screen.getByLabelText("Location"));
    await userEvent.type(screen.getByLabelText("Location"), "Dry box ");
    await userEvent.clear(screen.getByLabelText("Notes"));
    await userEvent.click(save);

    expect(onsave).toHaveBeenCalledWith({ location: "Dry box", notes: null });
    expect(await screen.findByRole("status")).toHaveTextContent("Saved");
  });

  it("reports a failed save", async () => {
    const onsave = vi.fn().mockRejectedValue(new Error("nope"));
    render(WhereNotes, { spool: spoolDetail(), canEdit: true, onsave });

    await userEvent.type(screen.getByLabelText("Notes"), "!");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Something went wrong");
  });

  it("shows location and notes read-only to viewers", () => {
    render(WhereNotes, { spool: spoolDetail({ notes: null }), canEdit: false, onsave: vi.fn() });

    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.getByText("Shelf A")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("shows tag data and both tag slots", () => {
    const { rerender } = render(TagData, { tags: [tag()] });
    expect(screen.getByText("PLA Basic")).toBeInTheDocument();
    expect(screen.getByText("not scanned yet")).toBeInTheDocument();
    expect(screen.queryByText("A1B2C3D4")).toBeNull();

    rerender({ tags: [tag({ decoded: null })] });
    expect(screen.getByText("The tag could not be decoded.")).toBeInTheDocument();

    rerender({ tags: [] });
    expect(screen.getByText(/No tag scanned yet/)).toBeInTheDocument();
  });
});

describe("products", () => {
  it("edits names and settings, and flags bad values", async () => {
    const items = [summary(), summary({ product: product({ id: 2, provisional: true }) })];
    const drafts = $state(Object.fromEntries(items.map((i) => [i.product.id, draftOf(i.product)])));
    render(ProductTable, { items, drafts });

    const [name] = screen.getAllByLabelText(/Display name for/);
    await userEvent.clear(name);
    expect(drafts[1].display_name).toBe("");
    expect(await screen.findByText("Enter a name.")).toBeInTheDocument();

    const [threshold] = screen.getAllByLabelText(/Low-stock threshold/);
    await userEvent.clear(threshold);
    await userEvent.type(threshold, "0");
    expect(drafts[1].low_stock_threshold).toBe(0);
    expect(screen.getByText("off")).toBeInTheDocument();
    expect(screen.getByText("Added by hand")).toBeInTheDocument();
    expect(screen.getByText("From tag")).toBeInTheDocument();
  });

  it("is read-only for viewers", () => {
    render(ProductTable, {
      items: [summary(), summary({ product: product({ id: 2, low_stock_threshold: 0 }) })],
      drafts: null,
    });

    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.getByText("off")).toBeInTheDocument();
    expect(screen.getAllByText("15%")).toHaveLength(2);
  });
});
