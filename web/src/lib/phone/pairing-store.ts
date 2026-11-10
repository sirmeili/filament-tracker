/** The phone's pairing (server, token, device ID), the tag key constant and the Cloudflare
 * Access service token, kept in the bridge's encrypted storage and nowhere else. */

import type { AccessToken } from "#lib/api/client.ts";
import { bridge } from "#lib/phone/bridge.ts";

export interface Pairing {
  url: string;
  token: string;
  deviceId: string;
}

const PAIRING_KEY = "pairing";
const SALT_KEY = "kdf_salt";
const ACCESS_KEY = "cf_access";

export async function loadPairing(): Promise<Pairing | null> {
  const text = await bridge().secureGet(PAIRING_KEY);
  if (!text) return null;
  try {
    const value = JSON.parse(text) as Partial<Pairing>;
    if (
      typeof value.url === "string" &&
      typeof value.token === "string" &&
      typeof value.deviceId === "string"
    ) {
      return { url: value.url, token: value.token, deviceId: value.deviceId };
    }
  } catch {
    // Unreadable: treat as not paired.
  }
  return null;
}

export async function savePairing(pairing: Pairing, salt: string): Promise<void> {
  await bridge().secureSet(PAIRING_KEY, JSON.stringify(pairing));
  await bridge().secureSet(SALT_KEY, salt);
}

export function loadSalt(): Promise<string | null> {
  return bridge().secureGet(SALT_KEY);
}

export async function saveSalt(salt: string): Promise<void> {
  await bridge().secureSet(SALT_KEY, salt);
}

export async function loadAccess(): Promise<AccessToken | null> {
  const text = await bridge().secureGet(ACCESS_KEY);
  if (!text) return null;
  try {
    const value = JSON.parse(text) as Partial<AccessToken>;
    if (typeof value.clientId === "string" && typeof value.clientSecret === "string") {
      return { clientId: value.clientId, clientSecret: value.clientSecret };
    }
  } catch {
    // Unreadable: treat as no token; the next visit home fetches it again.
  }
  return null;
}

/** Keep the server's Access token, or forget it when the server has none. */
export async function saveAccess(access: AccessToken | null): Promise<void> {
  if (access) await bridge().secureSet(ACCESS_KEY, JSON.stringify(access));
  else await bridge().secureRemove(ACCESS_KEY);
}

export async function forgetPairing(): Promise<void> {
  await bridge().secureRemove(PAIRING_KEY);
  await bridge().secureRemove(SALT_KEY);
  await bridge().secureRemove(ACCESS_KEY);
}
