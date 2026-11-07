/** Unpacking a delivery (docs/SPEC.md, Phone scanner): while Delivery is on, every spool
 * recorded on Scan joins a list for the session, so a whole box can be checked off.
 *
 * The list lives in memory: leaving Scan keeps it, closing the app ends it, and Clear
 * empties it. Clearing only empties the list; the recorded events stay.
 */

import type { ScanAction } from "#lib/phone/device-api.ts";
import type { Card, LastScan } from "#lib/phone/scan-flow.ts";

export interface DeliveryRow {
  eventId: string;
  card: Card;
  action: ScanAction;
  at: number;
  /** Still in the offline queue. */
  queued: boolean;
  undone: boolean;
}

export interface DeliveryTotals {
  received: number;
  opened: number;
  empty: number;
}

/** "4 new · 1 opened", with "· 2 empty" only when there are any. */
export function totalsText(totals: DeliveryTotals): string {
  const parts = [`${totals.received} new`, `${totals.opened} opened`];
  if (totals.empty > 0) parts.push(`${totals.empty} empty`);
  return parts.join(" · ");
}

export class Delivery {
  on = $state(false);
  rows = $state<DeliveryRow[]>([]);

  toggle(): void {
    this.on = !this.on;
  }

  clear(): void {
    this.rows = [];
  }

  /** Follow the Scan flow's last scan: a new one joins the list while Delivery is on, and
   * an undo marks its row. */
  seen(last: LastScan | null): void {
    if (!last) return;
    const row = this.rows.find((r) => r.eventId === last.eventId);
    if (row) {
      row.undone = last.undone;
      return;
    }
    if (!this.on || last.undone) return;
    this.rows.push({
      eventId: last.eventId,
      card: last.card,
      action: last.action,
      at: last.at,
      queued: last.queued,
      undone: false,
    });
  }

  /** Clear the queued marks of events that have since been sent. */
  sent(stillQueued: (eventId: string) => boolean): void {
    for (const row of this.rows) {
      if (row.queued && !stillQueued(row.eventId)) row.queued = false;
    }
  }

  get totals(): DeliveryTotals {
    const totals: DeliveryTotals = { received: 0, opened: 0, empty: 0 };
    for (const row of this.rows) {
      if (row.undone) continue;
      if (row.action === "received") totals.received += 1;
      else if (row.action === "opened") totals.opened += 1;
      else if (row.action === "empty") totals.empty += 1;
    }
    return totals;
  }
}
