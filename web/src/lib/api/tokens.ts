/** Machine tokens for Home Assistant and scripts, on the Settings page (Admin only). */

import { api } from "#lib/api/client.ts";
import { dateTime } from "#lib/format.ts";
import type { Role } from "#lib/roles.ts";

export interface MachineTokenOut {
  id: number;
  name: string;
  role: Role;
  created_at: string;
  /** The username of the admin who made it; null if made with a token. */
  created_by: string | null;
  last_used_at: string | null;
  revoked: boolean;
}

export interface MachineTokenCreated extends MachineTokenOut {
  /** Shown once; the server keeps only a hash. */
  token: string;
}

export function listTokens(): Promise<MachineTokenOut[]> {
  return api<MachineTokenOut[]>("/tokens");
}

export function createToken(name: string, role: Role): Promise<MachineTokenCreated> {
  return api<MachineTokenCreated>("/tokens", { method: "POST", body: { name, role } });
}

export function revokeToken(id: number): Promise<void> {
  return api<void>(`/tokens/${id}`, { method: "DELETE" });
}

/** "Made Oct 12, 4:05 PM by frank". */
export function madeText(token: MachineTokenOut, now: Date = new Date()): string {
  const by = token.created_by ? ` by ${token.created_by}` : "";
  return `Made ${dateTime(token.created_at, now)}${by}`;
}

/** "Never used" or "Last used Oct 12, 4:05 PM". */
export function usedText(token: MachineTokenOut, now: Date = new Date()): string {
  return token.last_used_at ? `Last used ${dateTime(token.last_used_at, now)}` : "Never used";
}
