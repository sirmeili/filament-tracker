/** Requests the phone makes as a scanner, with its device token (not a user session). */

import { ApiError, API_PREFIX, errorMessage } from "#lib/api/client.ts";
import type { Pairing } from "#lib/phone/pairing-store.ts";
import type { TagRead } from "#lib/phone/bridge.ts";

export type ScanAction = "received" | "opened" | "empty" | "lookup";
export type ScreenAction = "received" | "opened" | "empty" | "info" | "cancel";
export type Feedback =
  "ok" | "ok_created" | "already_in_state" | "flagged" | "unreadable" | "error";

export interface ScanEvent {
  event_id: string;
  device_id: string;
  action: ScanAction;
  tag_uid: string;
  blocks: string[];
  read_ok: boolean;
  scanned_at: string;
  fw_version: string;
}

export interface ScanProduct {
  id: number | null;
  display_name: string;
  filament_type: string;
  color_rgba: string;
  material_id: string | null;
  variant_id: string | null;
}

export interface ScanSpool {
  id: number;
  state: string;
  received_at: string | null;
  opened_at: string | null;
  emptied_at: string | null;
  remaining_pct: number | null;
}

export interface ScanResult {
  feedback: Feedback;
  event_id: string | null;
  state: string;
  product: ScanProduct | null;
  spool: ScanSpool | null;
  actions: (ScreenAction | null)[];
  suggested: ScreenAction | null;
  placeholder: boolean;
}

export function scanEvent(
  pairing: Pairing,
  read: TagRead,
  action: ScanAction,
  appVersion: string,
  now: Date = new Date(),
  eventId: string = crypto.randomUUID(),
): ScanEvent {
  return {
    event_id: eventId,
    device_id: pairing.deviceId,
    action,
    tag_uid: read.tagUid,
    blocks: read.blocks,
    read_ok: read.readOk,
    scanned_at: now.toISOString(),
    fw_version: appVersion,
  };
}

/** How long the phone waits for the server before treating it as offline. */
export const REQUEST_TIMEOUT_MS = 5000;

/** True when a request never got an answer, so it is worth queueing and retrying. */
export function isOffline(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 0 || error.status >= 500);
}

export class DeviceApi {
  constructor(
    private readonly pairing: Pairing,
    private readonly fetchFn: typeof fetch = (...args) => fetch(...args),
  ) {}

  scan(event: ScanEvent): Promise<ScanResult> {
    return this.request<ScanResult>("POST", "/scans", event);
  }

  revert(eventId: string): Promise<unknown> {
    return this.request("POST", `/events/${encodeURIComponent(eventId)}/revert`);
  }

  heartbeat(fwVersion: string, queueLength: number): Promise<unknown> {
    return this.request("POST", "/devices/heartbeat", {
      fw_version: fwVersion,
      queue_length: queueLength,
    });
  }

  /** Revoke this phone's own token, when it is unlinked. */
  unlink(): Promise<unknown> {
    return this.request("POST", "/devices/unlink");
  }

  async provisioning(): Promise<string> {
    const body = await this.request<{ kdf_salt: string }>("GET", "/devices/provisioning");
    return body.kdf_salt;
  }

  private async request<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
    const headers: Record<string, string> = {
      Accept: "application/json",
      Authorization: `Bearer ${this.pairing.token}`,
    };
    const init: RequestInit = { method, headers, credentials: "omit" };
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(body);
    }
    const { response, text } = await this.send(this.pairing.url + API_PREFIX + path, init);
    let parsed: unknown;
    try {
      parsed = text ? JSON.parse(text) : undefined;
    } catch {
      parsed = undefined;
    }
    if (!response.ok) {
      throw new ApiError(
        response.status,
        errorMessage(parsed, `Request failed (${response.status})`),
      );
    }
    return parsed as T;
  }

  /**
   * Fetch with a time limit. A server that is down behind a firewall, or a phone that has
   * left the Wi-Fi, may never answer at all; the scan must still fall back to offline.
   * Racing the timer works even where native HTTP ignores the abort signal.
   */
  private async send(
    url: string,
    init: RequestInit,
  ): Promise<{ response: Response; text: string }> {
    const abort = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const timeout = new Promise<never>((_, reject) => {
      timer = setTimeout(() => {
        abort.abort();
        reject(new Error("timed out"));
      }, REQUEST_TIMEOUT_MS);
    });
    const answer = (async () => {
      const response = await this.fetchFn(url, { ...init, signal: abort.signal });
      return { response, text: await response.text() };
    })();
    try {
      return await Promise.race([answer, timeout]);
    } catch {
      throw new ApiError(0, "Cannot reach the server");
    } finally {
      clearTimeout(timer);
      answer.catch(() => {});
    }
  }
}
