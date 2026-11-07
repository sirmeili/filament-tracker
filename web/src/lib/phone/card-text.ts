/** Words for the Scan screen's spool card. */

import type { SpoolState } from "#lib/api/types.ts";
import { shortDate, STATE_LABELS } from "#lib/format.ts";
import type { Card } from "#lib/phone/scan-flow.ts";
import type { NfcStatus } from "#lib/phone/bridge.ts";

/** The chip above the name: the spool's state, as on the scanner's card. */
export function chipText(card: Card): string {
  if (card.offline) return "Offline";
  if (card.state === null) return "Not tracked yet";
  return STATE_LABELS[card.state as SpoolState] ?? "Unknown";
}

/** The chip's style: a tracked state, or a dashed "new" chip for a tag not known yet. */
export function chipKind(card: Card): string {
  if (card.offline || card.state === null) return "new";
  return card.state in STATE_LABELS ? card.state : "unknown";
}

/** The line under the name: when the spool reached its state, and its number. */
export function cardLine(card: Card, now: Date = new Date()): string {
  if (card.offline) return "Read on the phone; your choice will be queued";
  const number = card.spoolId ? ` · #${card.spoolId}` : "";
  if (card.placeholder)
    return `Added by hand, received ${shortDate(card.receivedAt, now)}${number}`;
  switch (card.state) {
    case null:
      return "New tag";
    case "sealed":
      return `Received ${shortDate(card.receivedAt, now)}${number}`;
    case "open":
      return `Opened ${shortDate(card.openedAt, now)}${number}`;
    case "empty":
      return `Used up ${shortDate(card.emptiedAt, now)}${number}`;
    default:
      return `State unknown${number}`;
  }
}

export const NFC_MESSAGES: Record<Exclude<NfcStatus, "ready">, string> = {
  no_nfc: "This phone has no NFC, so it cannot read spools.",
  nfc_off: "NFC is off. Turn it on in Android's settings, then come back.",
  no_mifare:
    "This phone's NFC chip cannot read Bambu tags (MIFARE Classic). Most Google Pixel phones can.",
};
