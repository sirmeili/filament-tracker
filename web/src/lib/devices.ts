/** Helpers for the Devices page. */

import type { DeviceOut } from "#lib/api/types.ts";
import { shortDate } from "#lib/format.ts";

/** A device ID from its name: "Office scanner" -> "office-scanner". The server accepts
 * lower-case letters, digits and "-", up to 64 characters, starting with a letter or digit. */
export function deviceId(name: string): string {
  return name
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64)
    .replace(/-+$/, "");
}

export const DEVICE_ID_PATTERN = /^[a-z0-9][a-z0-9-]{0,63}$/;

/** "just now", "12 min ago", "2 h ago" or a date. */
export function ago(iso: string, now: Date = new Date()): string {
  const minutes = Math.floor((now.getTime() - new Date(iso).getTime()) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  if (minutes < 24 * 60) return `${Math.floor(minutes / 60)} h ago`;
  return shortDate(iso, now);
}

export type DeviceStatus = "online" | "offline" | "revoked";

export function deviceStatus(device: DeviceOut): DeviceStatus {
  if (device.revoked) return "revoked";
  return device.online ? "online" : "offline";
}

export const STATUS_LABELS: Record<DeviceStatus, string> = {
  online: "Online",
  offline: "Offline",
  revoked: "Revoked",
};

export function seenText(device: DeviceOut, now: Date = new Date()): string {
  return device.last_seen_at ? `Last seen ${ago(device.last_seen_at, now)}` : "Never seen";
}
