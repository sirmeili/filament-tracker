import { afterEach, describe, expect, it, vi } from "vitest";
import * as admin from "#lib/api/admin.ts";
import { fakeFetch } from "../../test/fixtures.ts";

afterEach(() => vi.unstubAllGlobals());

describe("admin API calls", () => {
  it("send the right method, path and body", async () => {
    const page = { items: [], total: 0, limit: 50, offset: 0 };
    const fetch = fakeFetch({
      "GET /review": { flagged_events: [], unidentified_tags: [], likely_empty: [] },
      "POST /review/events/e1/accept": {},
      "POST /review/events/e1/unaccept": {},
      "POST /review/tags/A%2FB/dismiss": null,
      "POST /review/tags/A%2FB/restore": null,
      "GET /events?limit=50&offset=0": page,
      "GET /events?limit=50&offset=50&source=ui": page,
      "GET /products": [],
      "POST /products": { id: 9 },
      "POST /spools": { id: 21 },
      "GET /devices": [],
      "POST /devices": { id: "shelf", token: "t" },
      "POST /devices/shelf/rotate": { id: "shelf", token: "t2" },
      "DELETE /devices/shelf": null,
      "GET /users": [],
      "POST /users": { id: 4 },
      "PATCH /users/4": { id: 4 },
      "POST /auth/password": null,
    });
    vi.stubGlobal("fetch", fetch);

    await admin.getReview();
    await admin.acceptEvent("e1");
    await admin.unacceptEvent("e1");
    await admin.dismissTag("A/B");
    await admin.restoreTag("A/B");
    expect((await admin.listEvents({ limit: 50, offset: 0 })).total).toBe(0);
    await admin.listEvents({ source: "ui", limit: 50, offset: 50 });
    await admin.listProducts();
    expect(
      (
        await admin.createProduct({
          display_name: "T",
          filament_type: "TPU",
          color_rgba: "000000FF",
        })
      ).id,
    ).toBe(9);
    await admin.addSpool({ product_id: 9, location: null, notes: "n" });
    await admin.listDevices();
    expect((await admin.registerDevice("shelf", "Shelf")).token).toBe("t");
    expect((await admin.rotateToken("shelf")).token).toBe("t2");
    await admin.revokeDevice("shelf");
    await admin.listUsers();
    await admin.createUser("sam", "viewer", "a long password");
    await admin.updateUser(4, { role: "editor" });
    await admin.changePassword("old", "new password!");

    expect(fetch.calls.filter((c) => c.method !== "GET")).toEqual([
      { method: "POST", path: "/review/events/e1/accept", body: undefined },
      { method: "POST", path: "/review/events/e1/unaccept", body: undefined },
      { method: "POST", path: "/review/tags/A%2FB/dismiss", body: undefined },
      { method: "POST", path: "/review/tags/A%2FB/restore", body: undefined },
      {
        method: "POST",
        path: "/products",
        body: { display_name: "T", filament_type: "TPU", color_rgba: "000000FF" },
      },
      { method: "POST", path: "/spools", body: { product_id: 9, location: null, notes: "n" } },
      { method: "POST", path: "/devices", body: { id: "shelf", name: "Shelf" } },
      { method: "POST", path: "/devices/shelf/rotate", body: undefined },
      { method: "DELETE", path: "/devices/shelf", body: undefined },
      {
        method: "POST",
        path: "/users",
        body: { username: "sam", role: "viewer", password: "a long password" },
      },
      { method: "PATCH", path: "/users/4", body: { role: "editor" } },
      {
        method: "POST",
        path: "/auth/password",
        body: { current_password: "old", new_password: "new password!" },
      },
    ]);
  });
});
