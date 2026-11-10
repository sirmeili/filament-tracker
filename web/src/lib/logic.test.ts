import { describe, expect, it } from "vitest";
import { ApiError } from "#lib/api/client.ts";
import { describeError } from "#lib/api/errors.ts";
import { spoolQuery } from "#lib/api/stock.ts";
import {
  dateTime,
  eventBy,
  eventTitle,
  hexText,
  shortDate,
  STATE_LABELS,
  swatchColor,
} from "#lib/format.ts";
import {
  changesFor,
  draftOf,
  draftProblem,
  sourceText,
  spoolCount,
  unsavedText,
} from "#lib/products.ts";
import {
  actionsFor,
  countText,
  knownLocations,
  nearlyOut,
  outcomeText,
  rangeText,
  selectionText,
  statusLine,
} from "#lib/spools.ts";
import { tagFields } from "#lib/tag-data.ts";
import { event, product, spoolRow, summary, tag } from "../test/fixtures.ts";

const NOW = new Date("2026-11-06T12:00:00Z");

describe("format", () => {
  it("turns the tag color into a swatch color", () => {
    expect(swatchColor("00ae42ff")).toBe("#00AE42");
    expect(hexText("FFFFFF80")).toBe("FFFFFF");
    expect(swatchColor("nope")).toBe("#808080");
  });

  it("calls the empty state Used up", () => {
    expect(STATE_LABELS.empty).toBe("Used up");
  });

  it("formats dates, with the year only when it differs", () => {
    expect(shortDate(null)).toBe("—");
    expect(shortDate("2026-10-12T12:00:00Z", NOW)).toBe("Oct 12");
    expect(shortDate("2025-10-12T12:00:00Z", NOW)).toBe("Oct 12, 2025");
    expect(dateTime("2026-10-12T12:00:00Z", NOW)).toMatch(/^Oct 12, \d{1,2}:00 (AM|PM)$/);
    expect(shortDate("2026-10-12T12:00:00Z")).toMatch(/^Oct 12/);
  });

  it("names events and who recorded them", () => {
    expect(eventTitle("empty")).toBe("Used up");
    expect(eventTitle("mystery")).toBe("mystery");
    expect(eventBy(event({ username: "frank", device_name: null }))).toBe("frank (web)");
    expect(eventBy(event({ username: "bob" }))).toBe("bob (Workbench scanner)");
    expect(eventBy(event())).toBe("Workbench scanner");
    expect(eventBy(event({ device_name: null, source: "ams" }))).toBe("AMS");
    expect(eventBy(event({ device_name: null, source: "ui" }))).toBe("Admin token");
    expect(eventBy(event({ device_name: null, source: "other" }))).toBe("other");
  });
});

describe("errors", () => {
  it.each([
    [new ApiError(0, "x"), "Cannot reach the server."],
    [new ApiError(403, "x"), "Your role cannot do that."],
    [new ApiError(404, "x"), "Not found. It may have been removed."],
    [new ApiError(409, "cannot undo an undo"), "cannot undo an undo."],
    [new ApiError(422, "Bad value."), "Bad value."],
    [new Error("odd"), "Something went wrong. Try again."],
  ])("describes %s", (error, text) => {
    expect(describeError(error)).toBe(text);
  });
});

describe("spoolQuery", () => {
  it("leaves out empty filters", () => {
    expect(spoolQuery({})).toBe("");
    expect(spoolQuery({ q: "  " })).toBe("");
    expect(
      spoolQuery({ states: ["open", "empty"], type: "PLA", q: " red ", limit: 50, offset: 50 }),
    ).toBe("?state=open&state=empty&type=PLA&q=red&limit=50&offset=50");
  });
});

describe("spools", () => {
  it("counts spools by state", () => {
    expect(countText([summary()])).toBe("5 spools · 1 sealed · 1 open · 3 used up");
    expect(countText([summary({ counts: { sealed: 1, open: 0, empty: 0, unknown: 2 } })])).toBe(
      "3 spools · 1 sealed · 0 open · 0 used up · 2 unknown",
    );
    expect(countText([summary({ counts: { sealed: 1, open: 0, empty: 0, unknown: 0 } })])).toBe(
      "1 spool · 1 sealed · 0 open · 0 used up",
    );
  });

  it("describes the page range and selection", () => {
    expect(rangeText(0, 13, 34)).toBe("Showing 1–13 of 34");
    expect(rangeText(0, 0, 0)).toBe("No spools match");
    expect(selectionText(1)).toBe("1 spool selected");
    expect(selectionText(3)).toBe("3 spools selected");
  });

  it("marks open spools at or below the product's cutoff as nearly out", () => {
    expect(nearlyOut(spoolRow({ remaining_pct: 15 }))).toBe(true);
    expect(nearlyOut(spoolRow({ remaining_pct: 16 }))).toBe(false);
    expect(nearlyOut(spoolRow({ remaining_pct: null }))).toBe(false);
    expect(nearlyOut(spoolRow({ state: "empty", remaining_pct: 0 }))).toBe(false);
  });

  it("suggests each location once", () => {
    const rows = [
      spoolRow({ location: "Shelf B" }),
      spoolRow({ location: "shelf b" }),
      spoolRow({ location: "Dry box" }),
      spoolRow({ location: null }),
      spoolRow({ location: "  " }),
    ];
    expect(knownLocations(rows)).toEqual(["Dry box", "Shelf B"]);
  });

  it("offers the scanner's next step first", () => {
    expect(actionsFor("sealed").map((a) => a.action)).toEqual(["opened", "empty"]);
    expect(actionsFor("open")).toEqual([{ action: "empty", label: "Mark used up", primary: true }]);
    expect(actionsFor("empty")[0].label).toBe("Reopen (correction)");
    expect(actionsFor("unknown").map((a) => a.action)).toEqual(["received", "opened"]);
  });

  it("summarises the state under the name", () => {
    expect(statusLine(spoolRow(), NOW)).toBe("Open since Oct 20 · received Oct 12");
    expect(statusLine(spoolRow({ received_at: null }), NOW)).toBe("Open since Oct 20");
    expect(statusLine(spoolRow({ state: "empty", emptied_at: "2026-11-01T12:00:00Z" }), NOW)).toBe(
      "Used up Nov 1 · opened Oct 20",
    );
    expect(statusLine(spoolRow({ state: "empty", opened_at: null }), NOW)).toBe("Used up —");
    expect(statusLine(spoolRow({ state: "sealed" }), NOW)).toBe("Sealed, received Oct 12");
    expect(statusLine(spoolRow({ state: "sealed", received_at: null }), NOW)).toBe("Sealed");
    expect(statusLine(spoolRow({ state: "unknown" }))).toMatch(/^No state/);
    expect(statusLine(spoolRow())).toMatch(/^Open since/);
  });

  it("explains the outcome of an action", () => {
    expect(outcomeText("applied", "open")).toBe("Recorded.");
    expect(outcomeText("already_in_state", "empty")).toBe("Already used up; nothing changed.");
    expect(outcomeText("flagged", "empty")).toMatch(/flagged for review/);
  });
});

describe("products", () => {
  const saved = product();

  it("says where a product came from", () => {
    expect(sourceText(saved)).toBe("From tag");
    expect(sourceText(product({ provisional: true }))).toBe("Added by hand");
    expect(sourceText(product({ provisional: true, from_ams: true }))).toBe("From the AMS");
    // Once a tag fills it in, it is a product from a tag.
    expect(sourceText(product({ from_ams: true }))).toBe("From tag");
  });

  it("finds only the changed fields", () => {
    expect(changesFor(saved, draftOf(saved))).toBeNull();
    expect(changesFor(saved, { ...draftOf(saved), display_name: " Black " })).toEqual({
      display_name: "Black",
    });
    expect(
      changesFor(saved, {
        display_name: saved.display_name,
        low_stock_threshold: 0,
        nearly_out_pct: 20,
      }),
    ).toEqual({ low_stock_threshold: 0, nearly_out_pct: 20 });
    expect(
      changesFor(saved, { ...draftOf(saved), low_stock_threshold: null, nearly_out_pct: null }),
    ).toEqual({ low_stock_threshold: undefined, nearly_out_pct: undefined });
  });

  it.each([
    [{ display_name: " " }, "Enter a name."],
    [{ display_name: "x".repeat(101) }, "Names are at most 100 characters."],
    [{ low_stock_threshold: null }, "Low at: a whole number, 0 to 1000."],
    [{ low_stock_threshold: 1.5 }, "Low at: a whole number, 0 to 1000."],
    [{ low_stock_threshold: 1001 }, "Low at: a whole number, 0 to 1000."],
    [{ nearly_out_pct: -1 }, "Nearly out: a whole number, 0 to 100."],
    [{ nearly_out_pct: 101 }, "Nearly out: a whole number, 0 to 100."],
    [{}, null],
  ])("checks drafts (%o)", (change, problem) => {
    expect(draftProblem({ ...draftOf(saved), ...change })).toBe(problem);
  });

  it("counts spools and changes", () => {
    expect(spoolCount(summary())).toBe(5);
    expect(unsavedText(1)).toBe("1 product changed");
    expect(unsavedText(2)).toBe("2 products changed");
  });
});

describe("tagFields", () => {
  it("lists the decoded fields the tag has", () => {
    expect(tagFields(tag().decoded)).toEqual([
      { label: "Material", value: "GFA00" },
      { label: "Variant", value: "A00-K00" },
      { label: "Type", value: "PLA Basic" },
      { label: "Diameter", value: "1.75 mm" },
      { label: "Weight", value: "1000 g" },
      { label: "Produced", value: "2026-09-18" },
    ]);
  });

  it("skips missing fields and falls back to the short type", () => {
    expect(tagFields({ filament_type: "PLA", filament_diameter_mm: null, variant_id: "" })).toEqual(
      [{ label: "Type", value: "PLA" }],
    );
    expect(tagFields(null)).toEqual([]);
  });
});
