/** First-start setup: shown instead of sign-in until the first Admin exists. */

import { api } from "#lib/api/client.ts";
import type { Me } from "#lib/api/types.ts";

export interface SetupStatus {
  open: boolean;
  /** Starter settings to ask for: those not already set on the server. */
  time_zone_needed: boolean;
  kdf_salt_needed: boolean;
}

export interface SetupFields {
  code: string;
  username: string;
  password: string;
  time_zone?: string;
  kdf_salt?: string;
}

/** The open setup, or null if it is closed or cannot be reached (it answers only on the
 * LAN, so through the reverse proxy it looks closed). */
export async function openSetup(): Promise<SetupStatus | null> {
  try {
    const status = await api<SetupStatus>("/setup");
    return status?.open ? status : null;
  } catch {
    return null;
  }
}

/** Create the first Admin; the server signs them in. */
export function finishSetup(fields: SetupFields): Promise<Me> {
  return api<Me>("/setup", { method: "POST", body: fields });
}
