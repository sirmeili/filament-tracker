/** The phone's pairing (server, token, device ID) and the tag key constant, kept in the
 * bridge's encrypted storage. The token and constant are never kept anywhere else. */

import { bridge } from "#lib/phone/bridge.ts";

export interface Pairing {
  url: string;
  token: string;
  deviceId: string;
}

const PAIRING_KEY = "pairing";
const SALT_KEY = "kdf_salt";

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

export async function forgetPairing(): Promise<void> {
  await bridge().secureRemove(PAIRING_KEY);
  await bridge().secureRemove(SALT_KEY);
}
