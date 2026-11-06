import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getInventory,
  getSpool,
  listSpools,
  moveSpools,
  recordAction,
  reviewCount,
  undoEvent,
  updateProduct,
  updateSpool,
} from "#lib/api/stock.ts";
import { fakeFetch, spoolDetail, summary } from "../../test/fixtures.ts";

afterEach(() => vi.unstubAllGlobals());

describe("stock API calls", () => {
  it("send the right method, path and body", async () => {
    const fetch = fakeFetch({
      "GET /inventory": [summary()],
      "GET /spools?state=open&limit=50": { items: [], total: 0, limit: 50, offset: 0 },
      "GET /spools/4": spoolDetail({ id: 4 }),
      "PATCH /spools/4": spoolDetail({ id: 4, location: "Bin" }),
      "PATCH /spools": [],
      "POST /spools/4/events": { outcome: "applied" },
      "POST /events/e1/revert": {},
      "PATCH /products/2": { id: 2 },
      "GET /review": {
        flagged_events: [{}, {}],
        unidentified_tags: [{ uid: "X" }],
        likely_empty: [],
      },
    });
    vi.stubGlobal("fetch", fetch);

    expect(await getInventory()).toHaveLength(1);
    expect((await listSpools({ states: ["open"], limit: 50 })).total).toBe(0);
    expect((await getSpool(4)).id).toBe(4);
    expect((await updateSpool(4, { location: "Bin" })).location).toBe("Bin");
    await moveSpools([1, 2], null);
    await recordAction(4, "opened");
    await undoEvent("e1");
    await updateProduct(2, { nearly_out_pct: 20 });
    expect(await reviewCount()).toBe(3);

    expect(fetch.calls.filter((c) => c.method !== "GET")).toEqual([
      { method: "PATCH", path: "/spools/4", body: { location: "Bin" } },
      { method: "PATCH", path: "/spools", body: { spool_ids: [1, 2], location: null } },
      { method: "POST", path: "/spools/4/events", body: { action: "opened" } },
      { method: "POST", path: "/events/e1/revert", body: undefined },
      { method: "PATCH", path: "/products/2", body: { nearly_out_pct: 20 } },
    ]);
  });
});
