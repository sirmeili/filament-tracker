/** The phone app's running scanner: pairing, queue, scan flow, heartbeat and retries.
 *
 * Started when the app opens (if it is paired) and stopped when it closes. Every 5 minutes,
 * and when the app comes back to the front, it sends a heartbeat with the queue size.
 * Queued scans are retried when due, and all of them at once as soon as the server answers
 * again (a heartbeat, a lookup or any other request). Away from home the server answers
 * but refuses scans, so they stay queued until the phone is home.
 *
 * At start and whenever the app comes back to the front, the first heartbeat that reaches
 * the server at home also fetches the tag key constant and the Access token again, so a
 * token replaced on the server reaches the phone without pairing again.
 */

import { setAccessToken, type AccessToken } from "#lib/api/client.ts";
import { bridge, type PhoneBridge } from "#lib/phone/bridge.ts";
import { DeviceApi, reachOf, type Reach } from "#lib/phone/device-api.ts";
import {
  loadAccess,
  loadPairing,
  loadRecords,
  loadSalt,
  saveAccess,
  saveRecords,
  saveSalt,
  type Pairing,
} from "#lib/phone/pairing-store.ts";
import { OfflineQueue, type QueueStore } from "#lib/phone/queue.ts";
import { ScanFlow } from "#lib/phone/scan-flow.ts";

export const HEARTBEAT_MS = 5 * 60_000;
const QUEUE_KEY = "queue";

export function queueStore(native: PhoneBridge): QueueStore {
  return {
    load: () => native.secureGet(QUEUE_KEY),
    save: (text) => native.secureSet(QUEUE_KEY, text),
  };
}

export class PhoneSession {
  readonly flow: ScanFlow;
  /** How the last request reached the server; null until the first answer. */
  reach: Reach | null = null;
  /** The Access token sent with every request, when the server has one. */
  access: AccessToken | null = null;
  /** Whether this phone records actions: false for a Viewer's phone (it only looks up). */
  records = true;
  private reachListeners = new Set<(reach: Reach) => void>();
  private refreshDue = true;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private unsubscribe: (() => void) | null = null;
  private flushing: Promise<void> | null = null;
  private readonly onVisible = () => {
    if (document.visibilityState !== "visible") return;
    this.refreshDue = true;
    void this.beat();
  };

  constructor(
    readonly pairing: Pairing,
    public salt: string,
    readonly api: DeviceApi,
    readonly queue: OfflineQueue,
    private readonly native: PhoneBridge,
  ) {
    this.flow = new ScanFlow({
      api,
      queue,
      pairing,
      appVersion: native.appVersion,
      onReach: (reach) => this.reached(reach),
      records: () => this.records,
    });
  }

  /** Follow the Online / Offline / Away status; called at once with the current one. */
  subscribeReach(listener: (reach: Reach) => void): () => void {
    this.reachListeners.add(listener);
    if (this.reach !== null) listener(this.reach);
    return () => this.reachListeners.delete(listener);
  }

  private reached(reach: Reach): void {
    if (this.reach === reach) return;
    this.reach = reach;
    this.reachListeners.forEach((listener) => listener(reach));
    // The server is back: send what was queued now, not when its backoff runs out.
    if (reach === "online" && this.queue.size > 0) void this.retry(true);
  }

  /** The session for this phone, or null if it has not been paired. */
  static async open(
    native: PhoneBridge = bridge(),
    fetchFn?: typeof fetch,
  ): Promise<PhoneSession | null> {
    const pairing = await loadPairing();
    const salt = await loadSalt();
    if (!pairing || !salt) return null;
    const queue = await OfflineQueue.open(queueStore(native));
    const session = new PhoneSession(pairing, salt, new DeviceApi(pairing, fetchFn), queue, native);
    session.access = await loadAccess();
    session.records = await loadRecords();
    return session;
  }

  start(): void {
    setAccessToken(this.access);
    this.unsubscribe = this.queue.subscribe(() => this.scheduleRetry());
    void this.beat();
    this.heartbeatTimer = setInterval(() => void this.beat(), HEARTBEAT_MS);
    this.scheduleRetry();
    document.addEventListener("visibilitychange", this.onVisible);
  }

  stop(): void {
    document.removeEventListener("visibilitychange", this.onVisible);
    if (this.heartbeatTimer !== null) clearInterval(this.heartbeatTimer);
    if (this.retryTimer !== null) clearTimeout(this.retryTimer);
    this.heartbeatTimer = this.retryTimer = null;
    this.unsubscribe?.();
    this.flow.stop();
  }

  /** Send a heartbeat, then retry the queue if the server answered. */
  async beat(): Promise<void> {
    try {
      await this.api.heartbeat(this.native.appVersion, this.queue.size);
    } catch (error) {
      this.reached(reachOf(error));
      return; // The next heartbeat tries again.
    }
    this.reached("online");
    await this.refresh();
    await this.retry(true);
  }

  /** Fetch the tag key constant and the Access token again, once per start or return to the
   * front. A failure leaves the stored ones in use and tries again on the next heartbeat. */
  private async refresh(): Promise<void> {
    if (!this.refreshDue) return;
    this.refreshDue = false;
    try {
      const fresh = await this.api.provisioning();
      await saveSalt(fresh.salt);
      await saveAccess(fresh.access);
      await saveRecords(fresh.records);
      this.records = fresh.records;
      this.salt = fresh.salt;
      this.access = fresh.access;
      setAccessToken(fresh.access);
    } catch {
      this.refreshDue = true;
    }
  }

  /** Send the queue: what is due, or everything with `all`. One send runs at a time. */
  async retry(all = false): Promise<void> {
    if (this.flushing) return this.flushing;
    this.flushing = (async () => {
      try {
        await this.queue.flush((event) => this.api.scan(event), Date.now(), all);
      } finally {
        this.flushing = null;
      }
    })();
    return this.flushing;
  }

  private scheduleRetry(): void {
    if (this.retryTimer !== null) clearTimeout(this.retryTimer);
    this.retryTimer = null;
    const due = this.queue.nextDue();
    if (due === null) return;
    this.retryTimer = setTimeout(
      () => {
        this.retryTimer = null;
        void this.retry().then(() => this.scheduleRetry());
      },
      Math.max(due - Date.now(), 0),
    );
  }
}
