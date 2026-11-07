/** Scans chosen while the server could not be reached, kept until they are delivered.
 *
 * Like the scanner: at least 50 (here 100) are kept, retried with exponential backoff, and
 * each keeps its `event_id`, so a retry of one that did arrive is not counted twice. The
 * server replays events by when they happened, so delivery order does not matter.
 */

import { ApiError } from "#lib/api/client.ts";
import { isOffline, type ScanEvent } from "#lib/phone/device-api.ts";

export const QUEUE_LIMIT = 100;
export const BACKOFF_FIRST_MS = 5_000;
export const BACKOFF_MAX_MS = 5 * 60_000;

export interface QueueStore {
  load(): Promise<string | null>;
  save(text: string): Promise<void>;
}

interface Queued {
  event: ScanEvent;
  attempts: number;
  nextAt: number;
}

export function backoff(attempts: number): number {
  return Math.min(BACKOFF_FIRST_MS * 2 ** Math.max(attempts - 1, 0), BACKOFF_MAX_MS);
}

export interface FlushResult {
  sent: number;
  /** Refused by the server (for example, a revoked token); these are not retried. */
  refused: number;
  /** Still waiting, because the server could not be reached. */
  waiting: number;
}

export class OfflineQueue {
  private items: Queued[] = [];
  private listeners = new Set<(size: number) => void>();

  private constructor(private readonly store: QueueStore) {}

  static async open(store: QueueStore): Promise<OfflineQueue> {
    const queue = new OfflineQueue(store);
    const text = await store.load();
    if (text) {
      try {
        const items = JSON.parse(text) as Queued[];
        if (Array.isArray(items)) queue.items = items.filter((i) => i && i.event);
      } catch {
        // A corrupt queue is dropped rather than blocking the app.
      }
    }
    return queue;
  }

  get size(): number {
    return this.items.length;
  }

  /** Called with the new size whenever it changes. */
  subscribe(listener: (size: number) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  /** Queue an event; false when the queue is full. */
  async add(event: ScanEvent, now: number = Date.now()): Promise<boolean> {
    if (this.items.length >= QUEUE_LIMIT) return false;
    this.items.push({ event, attempts: 0, nextAt: now });
    await this.changed();
    return true;
  }

  /** Take an event back out (an undo before it was delivered); false if it is not queued. */
  async remove(eventId: string): Promise<boolean> {
    const before = this.items.length;
    this.items = this.items.filter((item) => item.event.event_id !== eventId);
    if (this.items.length === before) return false;
    await this.changed();
    return true;
  }

  /** When the next retry is due, or null if the queue is empty. */
  nextDue(): number | null {
    return this.items.length ? Math.min(...this.items.map((i) => i.nextAt)) : null;
  }

  /** Send every event that is due (every event with `all`, once the server is known to be
   * back). Stops at the first one the server cannot be reached for. */
  async flush(
    send: (event: ScanEvent) => Promise<unknown>,
    now: number = Date.now(),
    all = false,
  ): Promise<FlushResult> {
    const result: FlushResult = { sent: 0, refused: 0, waiting: 0 };
    const keep: Queued[] = [];
    let reachable = true;
    for (const item of this.items) {
      if (!reachable || (!all && item.nextAt > now)) {
        keep.push(item);
        continue;
      }
      try {
        await send(item.event);
        result.sent += 1;
      } catch (error) {
        if (isOffline(error) || !(error instanceof ApiError)) {
          reachable = false;
          const attempts = item.attempts + 1;
          keep.push({ ...item, attempts, nextAt: now + backoff(attempts) });
        } else {
          result.refused += 1;
        }
      }
    }
    result.waiting = keep.length;
    const changed = keep.length !== this.items.length || !reachable;
    this.items = keep;
    if (changed) await this.changed();
    return result;
  }

  private async changed(): Promise<void> {
    await this.store.save(JSON.stringify(this.items));
    this.listeners.forEach((listener) => listener(this.items.length));
  }
}
