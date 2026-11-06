/** Pairing the phone app: a QR code holding the server address and a device token. */

import { encode } from "uqr";

export const PAIRING_VERSION = 1;

/** Why a server address cannot be used, or null if it can. */
export function serverUrlError(text: string): string | null {
  let url: URL;
  try {
    url = new URL(text.trim());
  } catch {
    return "Enter a full address, such as https://filament.example.com.";
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    return "The address must start with http:// or https://.";
  }
  if (url.username || url.password) return "The address must not include a user name.";
  if (url.search || url.hash) return "The address must not include ? or #.";
  return null;
}

/** The address without a trailing slash, as the app stores it. */
export function normalizeUrl(text: string): string {
  const url = new URL(text.trim());
  return `${url.origin}${url.pathname.replace(/\/+$/, "")}`;
}

/** What the QR code holds. The app reads `v` first, so the format can change later. */
export function pairingPayload(serverUrl: string, token: string, deviceId: string): string {
  return JSON.stringify({
    v: PAIRING_VERSION,
    url: normalizeUrl(serverUrl),
    token,
    device_id: deviceId,
  });
}

/** The QR code as one SVG path of dark modules, with its size including the border. */
export function qrPath(text: string): { size: number; path: string } {
  const qr = encode(text, { ecc: "M", border: 2 });
  const parts: string[] = [];
  qr.data.forEach((row, y) =>
    row.forEach((dark, x) => {
      if (dark) parts.push(`M${x} ${y}h1v1h-1z`);
    }),
  );
  return { size: qr.size, path: parts.join("") };
}

const TOKEN_PATTERN = /^ftd_[A-Za-z0-9_-]{20,200}$/;
const DEVICE_ID_PATTERN = /^[a-z0-9][a-z0-9-]{0,63}$/;

export interface PairingFields {
  url: string;
  token: string;
  deviceId: string;
}

/** Check typed or scanned pairing details; the fields, or why they cannot be used. */
export function checkPairing(
  url: string,
  token: string,
  deviceId: string,
): { pairing: PairingFields } | { error: string } {
  const urlProblem = serverUrlError(url);
  if (urlProblem) return { error: urlProblem };
  if (!TOKEN_PATTERN.test(token.trim())) {
    return { error: "That is not a device token. It starts with ftd_." };
  }
  if (!DEVICE_ID_PATTERN.test(deviceId.trim())) {
    return { error: "The device ID uses lower-case letters, digits and dashes." };
  }
  return { pairing: { url: normalizeUrl(url), token: token.trim(), deviceId: deviceId.trim() } };
}

/** Read the text of a pairing QR code. */
export function parsePairing(text: string): { pairing: PairingFields } | { error: string } {
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch {
    return { error: "This is not a Filament Tracker pairing code." };
  }
  if (!value || typeof value !== "object") {
    return { error: "This is not a Filament Tracker pairing code." };
  }
  const fields = value as Record<string, unknown>;
  if (fields.v !== PAIRING_VERSION) {
    return { error: "This pairing code is from a different version. Update the app." };
  }
  const { url, token, device_id: deviceId } = fields;
  if (typeof url !== "string" || typeof token !== "string" || typeof deviceId !== "string") {
    return { error: "This pairing code is incomplete. Show a new one on the Devices page." };
  }
  return checkPairing(url, token, deviceId);
}
