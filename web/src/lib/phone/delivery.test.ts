import { describe, expect, it } from "vitest";
import { Delivery, totalsText } from "#lib/phone/delivery.svelte.ts";
import type { Card, LastScan } from "#lib/phone/scan-flow.ts";

const card: Card = {
  name: "Black PLA Basic",
  colorRgba: "000000FF",
  state: "sealed",
  receivedAt: null,
  openedAt: null,
  emptiedAt: null,
  remainingPct: null,
  spoolId: 7,
  placeholder: false,
  offline: false,
};

const scan = (eventId: string, fields: Partial<LastScan> = {}): LastScan => ({
  card,
  tagUid: "AA",
  action: "received",
  eventId,
  at: 1000,
  queued: false,
  undone: false,
  ...fields,
});

describe("delivery list", () => {
  it("keeps the spools recorded while it is on, each once", () => {
    const delivery = new Delivery();
    delivery.seen(scan("before")); // off: not listed
    delivery.toggle();
    delivery.seen(null);
    delivery.seen(scan("e1"));
    delivery.seen(scan("e1")); // the same scan seen again
    delivery.seen(scan("e2", { action: "opened" }));

    expect(delivery.rows.map((r) => r.eventId)).toEqual(["e1", "e2"]);
    expect(delivery.totals).toEqual({ received: 1, opened: 1, empty: 0 });
  });

  it("marks an undone scan, and leaves it out of the totals", () => {
    const delivery = new Delivery();
    delivery.on = true;
    delivery.seen(scan("e1"));
    delivery.seen(scan("e1", { undone: true }));
    delivery.seen(scan("e2", { undone: true })); // undone before it was listed

    expect(delivery.rows).toHaveLength(1);
    expect(delivery.rows[0].undone).toBe(true);
    expect(delivery.totals).toEqual({ received: 0, opened: 0, empty: 0 });
  });

  it("keeps marking rows after Delivery is turned off", () => {
    const delivery = new Delivery();
    delivery.on = true;
    delivery.seen(scan("e1"));
    delivery.toggle();
    delivery.seen(scan("e1", { undone: true }));
    expect(delivery.rows[0].undone).toBe(true);
  });

  it("drops the queued mark once an event has been sent", () => {
    const delivery = new Delivery();
    delivery.on = true;
    delivery.seen(scan("e1", { queued: true }));
    delivery.seen(scan("e2", { queued: true }));

    delivery.sent((id) => id === "e2");

    expect(delivery.rows.map((r) => r.queued)).toEqual([false, true]);
  });

  it("empties on Clear", () => {
    const delivery = new Delivery();
    delivery.on = true;
    delivery.seen(scan("e1", { action: "empty" }));
    expect(delivery.totals.empty).toBe(1);
    delivery.clear();
    expect(delivery.rows).toEqual([]);
    expect(delivery.on).toBe(true);
  });

  it("says the totals, with empty only when there are any", () => {
    expect(totalsText({ received: 4, opened: 0, empty: 0 })).toBe("4 new · 0 opened");
    expect(totalsText({ received: 1, opened: 2, empty: 3 })).toBe("1 new · 2 opened · 3 empty");
  });
});
