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
  if (isLoopbackHost(url.hostname)) {
    return "The phone can't reach localhost: on the phone, it means the phone itself. Use this computer's network address, such as http://192.168.1.20:8000.";
  }
  if (url.protocol === "http:" && !isLanHost(url.hostname)) {
    return "Plain http:// works only for addresses on your home network. Use https://.";
  }
  return null;
}

/** Loopback addresses: on a phone they name the phone, never the server. */
export function isLoopbackHost(hostname: string): boolean {
  const host = hostname.toLowerCase().replace(/\.$/, "");
  return (
    host === "localhost" ||
    host.endsWith(".localhost") ||
    host === "[::1]" ||
    host === "0.0.0.0" ||
    /^127\.\d+\.\d+\.\d+$/.test(host)
  );
}

const LAN_SUFFIXES = [".local", ".lan", ".home.arpa"];

/** Whether a host is on the home network, where the app allows plain HTTP (docs/SPEC.md). */
export function isLanHost(hostname: string): boolean {
  const host = hostname.toLowerCase().replace(/\.$/, "");
  if (host.startsWith("[")) {
    const ip6 = host.slice(1, -1);
    return ip6 === "::1" || /^f[cd][0-9a-f]{0,2}:/.test(ip6) || /^fe[89ab][0-9a-f]?:/.test(ip6);
  }
  const ip4 = host.match(/^(\d+)\.(\d+)\.\d+\.\d+$/);
  if (ip4) {
    const [a, b] = [Number(ip4[1]), Number(ip4[2])];
    return (
      a === 10 ||
      a === 127 ||
      (a === 172 && b >= 16 && b <= 31) ||
      (a === 192 && b === 168) ||
      (a === 169 && b === 254)
    );
  }
  if (host === "localhost" || !host.includes(".")) return true;
  return LAN_SUFFIXES.some((suffix) => host.endsWith(suffix));
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
    return { error: "This is not a RollCall pairing code." };
  }
  if (!value || typeof value !== "object") {
    return { error: "This is not a RollCall pairing code." };
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
