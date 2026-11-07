/** The phone app's state for the pages: whether it is paired, its session and queue size. */

import { ApiError, setApiBase } from "#lib/api/client.ts";
import type { PairingFields } from "#lib/pairing.ts";
import { bridge } from "#lib/phone/bridge.ts";
import { DeviceApi } from "#lib/phone/device-api.ts";
import { Delivery } from "#lib/phone/delivery.svelte.ts";
import { forgetPairing, savePairing } from "#lib/phone/pairing-store.ts";
import { PhoneSession } from "#lib/phone/session.ts";

/** What went wrong while pairing, in words. */
export function pairingError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 0) return "Can't reach that server. Check the address and your Wi-Fi.";
    if (error.status === 401) return "The server did not accept this token. Show a new code.";
    if (error.status === 403) return "The server accepts devices only from your home network.";
    if (error.status === 503) {
      return "The server has no tag key constant yet. Set BAMBU_KDF_SALT on the server.";
    }
  }
  return "Pairing failed. Try again.";
}

export const PHONE_PATHS = ["/scan", "/pair"] as const;

export function isPhonePath(pathname: string): boolean {
  return PHONE_PATHS.some((path) => pathname === path || pathname.startsWith(path + "/"));
}

class PhoneState {
  loaded = $state(false);
  session = $state<PhoneSession | null>(null);
  queueSize = $state(0);
  /** Whether the server answered the last request; null until it is known. */
  online = $state<boolean | null>(null);
  /** The Delivery list, kept while the app is open. */
  readonly delivery = new Delivery();
  private unsubscribe: (() => void) | null = null;

  get app(): boolean {
    return bridge().app;
  }

  get paired(): boolean {
    return this.session !== null;
  }

  async load(fetchFn?: typeof fetch): Promise<void> {
    if (this.app) this.attach(await PhoneSession.open(bridge(), fetchFn));
    this.loaded = true;
  }

  /** Check the details with the server, fetch the tag key constant, and keep both. */
  async pair(fields: PairingFields, fetchFn?: typeof fetch): Promise<void> {
    const salt = await new DeviceApi(fields, fetchFn).provisioning();
    await savePairing(fields, salt);
    this.attach(await PhoneSession.open(bridge(), fetchFn));
  }

  async unpair(): Promise<void> {
    await forgetPairing();
    this.attach(null);
    this.delivery.clear();
    this.delivery.on = false;
  }

  private attach(session: PhoneSession | null): void {
    this.unsubscribe?.();
    this.unsubscribe = null;
    this.session?.stop();
    this.session = session;
    setApiBase(session ? session.pairing.url : "");
    this.queueSize = session ? session.queue.size : 0;
    this.online = null;
    if (session) {
      const queue = session.queue.subscribe((size) => {
        this.queueSize = size;
        this.delivery.sent((id) => session.queue.has(id));
      });
      const online = session.subscribeOnline((value) => (this.online = value));
      const flow = session.flow.subscribe((view) => this.delivery.seen(view.last));
      this.unsubscribe = () => {
        queue();
        online();
        flow();
      };
      session.start();
    }
  }
}

export const phone = new PhoneState();
