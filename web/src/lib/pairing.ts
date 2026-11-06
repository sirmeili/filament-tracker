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
export function pairingPayload(serverUrl: string, token: string): string {
  return JSON.stringify({ v: PAIRING_VERSION, url: normalizeUrl(serverUrl), token });
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
