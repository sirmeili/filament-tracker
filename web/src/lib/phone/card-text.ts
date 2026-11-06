/** Words for the Scan screen's spool card. */

import { shortDate } from "#lib/format.ts";
import type { Card } from "#lib/phone/scan-flow.ts";
import type { NfcStatus } from "#lib/phone/bridge.ts";

/** "Sealed, received Oct 12", like the scanner's card. */
export function stateText(card: Card, now: Date = new Date()): string {
  if (card.offline) return "Offline, so its state is not known";
  if (card.placeholder) return `Added by hand, received ${shortDate(card.receivedAt, now)}`;
  switch (card.state) {
    case null:
      return "Not tracked yet";
    case "sealed":
      return `Sealed, received ${shortDate(card.receivedAt, now)}`;
    case "open":
      return `Open, opened ${shortDate(card.openedAt, now)}`;
    case "empty":
      return `Empty, used up ${shortDate(card.emptiedAt, now)}`;
    default:
      return "State unknown";
  }
}

export const NFC_MESSAGES: Record<Exclude<NfcStatus, "ready">, string> = {
  no_nfc: "This phone has no NFC, so it cannot read spools.",
  nfc_off: "NFC is off. Turn it on in Android's settings, then come back.",
  no_mifare:
    "This phone's NFC chip cannot read Bambu tags (MIFARE Classic). Most Google Pixel phones can.",
};
