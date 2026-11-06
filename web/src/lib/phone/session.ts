/** The phone app's running scanner: pairing, queue, scan flow, heartbeat and retries.
 *
 * Started when the app opens (if it is paired) and stopped when it closes. Every 5 minutes
 * it sends a heartbeat with the queue size; queued scans are retried when due and after
 * each heartbeat that gets through.
 */

import { bridge, type PhoneBridge } from "#lib/phone/bridge.ts";
import { DeviceApi, isOffline } from "#lib/phone/device-api.ts";
import { loadPairing, loadSalt, type Pairing } from "#lib/phone/pairing-store.ts";
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
  /** Whether the server answered the last request; null until the first answer. */
  online: boolean | null = null;
  private onlineListeners = new Set<(online: boolean) => void>();
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private unsubscribe: (() => void) | null = null;

  constructor(
    readonly pairing: Pairing,
    readonly salt: string,
    readonly api: DeviceApi,
    readonly queue: OfflineQueue,
    private readonly native: PhoneBridge,
  ) {
    this.flow = new ScanFlow({
      api,
      queue,
      pairing,
      appVersion: native.appVersion,
      onReach: (online) => this.reached(online),
    });
  }

  /** Follow the Online / Offline status; called at once with the current one, if known. */
  subscribeOnline(listener: (online: boolean) => void): () => void {
    this.onlineListeners.add(listener);
    if (this.online !== null) listener(this.online);
    return () => this.onlineListeners.delete(listener);
  }

  private reached(online: boolean): void {
    if (this.online === online) return;
    this.online = online;
    this.onlineListeners.forEach((listener) => listener(online));
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
    return new PhoneSession(pairing, salt, new DeviceApi(pairing, fetchFn), queue, native);
  }

  start(): void {
    this.unsubscribe = this.queue.subscribe(() => this.scheduleRetry());
    void this.beat();
    this.heartbeatTimer = setInterval(() => void this.beat(), HEARTBEAT_MS);
    this.scheduleRetry();
  }

  stop(): void {
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
      this.reached(!isOffline(error));
      return; // The next heartbeat tries again.
    }
    this.reached(true);
    await this.retry();
  }

  async retry(): Promise<void> {
    await this.queue.flush((event) => this.api.scan(event));
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
