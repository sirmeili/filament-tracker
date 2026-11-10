/** The phone app's state for the pages: whether it is paired, its session and queue size. */

import { ApiError, setAccessToken, setApiBase } from "#lib/api/client.ts";
import type { PairingFields } from "#lib/pairing.ts";
import { bridge } from "#lib/phone/bridge.ts";
import { DeviceApi, type Reach } from "#lib/phone/device-api.ts";
import { Delivery } from "#lib/phone/delivery.svelte.ts";
import { forgetPairing, saveAccess, savePairing } from "#lib/phone/pairing-store.ts";
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
  /** How the last request reached the server (Online, Offline, Away); null until known. */
  reach = $state<Reach | null>(null);
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
    const { salt, access } = await new DeviceApi(fields, fetchFn).provisioning();
    await savePairing(fields, salt);
    await saveAccess(access);
    this.attach(await PhoneSession.open(bridge(), fetchFn));
  }

  /**
   * Unlink this phone: revoke its token on the server if the server answers, then forget the
   * pairing here whatever happens, so a phone whose server is gone can still be unlinked.
   * Returns whether the token is known to be revoked.
   */
  async unlink(): Promise<boolean> {
    let revoked = false;
    if (this.session) {
      try {
        await this.session.api.unlink();
        revoked = true;
      } catch (error) {
        // 401: the server no longer accepts the token, so it is revoked already.
        revoked = error instanceof ApiError && error.status === 401;
      }
    }
    await this.unpair();
    return revoked;
  }

  /** Forget the pairing, the tag key constant and the queue on this phone. */
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
    if (!session) setAccessToken(null);
    this.queueSize = session ? session.queue.size : 0;
    this.reach = null;
    if (session) {
      const queue = session.queue.subscribe((size) => {
        this.queueSize = size;
        this.delivery.sent((id) => session.queue.has(id));
      });
      const reach = session.subscribeReach((value) => (this.reach = value));
      const flow = session.flow.subscribe((view) => this.delivery.seen(view.last));
      this.unsubscribe = () => {
        queue();
        reach();
        flow();
      };
      session.start();
    }
  }
}

export const phone = new PhoneState();
