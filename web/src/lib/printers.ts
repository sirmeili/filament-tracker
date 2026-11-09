/** Helpers for showing printers and AMS slots. */

import type { PrinterCheck, PrinterFields } from "#lib/api/admin.ts";
import type { AmsSlotRef, PrinterOut } from "#lib/api/types.ts";
import { ago } from "#lib/devices.ts";

// AMS units are 0 to 3; an AMS HT (one slot) is numbered from 128.
const HT_FIRST = 128;

/** "AMS 1", or "AMS HT 1" for the first AMS HT. */
export function amsName(amsIndex: number): string {
  return amsIndex >= HT_FIRST ? `AMS HT ${amsIndex - HT_FIRST + 1}` : `AMS ${amsIndex + 1}`;
}

/** "AMS 1, slot 2" from 0-based indexes; just "AMS HT 1" for its only slot. */
export function slotName(amsIndex: number, trayIndex: number): string {
  const name = amsName(amsIndex);
  return amsIndex >= HT_FIRST ? name : `${name}, slot ${trayIndex + 1}`;
}

/** "AMS 1, slot 2 on P1S". */
export function slotText(slot: AmsSlotRef): string {
  return `${slotName(slot.ams_index, slot.tray_index)} on ${slot.printer_name}`;
}

export type PrinterStatus = "online" | "offline" | "pin_mismatch" | "not_configured";

export function printerStatus(printer: PrinterOut): PrinterStatus {
  if (printer.connection === "pin_mismatch") return "pin_mismatch";
  if (!printer.configured) return "not_configured";
  return printer.online ? "online" : "offline";
}

export const PRINTER_STATUS_LABELS: Record<PrinterStatus, string> = {
  online: "Online",
  offline: "Offline",
  pin_mismatch: "Pin mismatch",
  not_configured: "Not connecting",
};

/** Why a printer is not connecting, when it is down to its access code. */
export function accessCodeNote(printer: PrinterOut): string | null {
  if (printer.access_code_unreadable)
    return "The saved access code can't be read with this server's key. Enter it again.";
  if (!printer.access_code_set) return "No access code saved, so the server is not connecting.";
  return null;
}

/** What the form holds: text boxes, so the port is a string until saved. */
export interface PrinterDraft {
  name: string;
  host: string;
  port: string;
  serial: string;
  access_code: string;
}

export function draftOf(printer?: PrinterOut): PrinterDraft {
  return {
    name: printer?.name ?? "",
    host: printer?.host ?? "",
    port: String(printer?.port ?? 8883),
    serial: printer?.serial ?? "",
    access_code: "",
  };
}

const HOST = /^[A-Za-z0-9.:[\]-]{1,255}$/;
const SERIAL = /^[A-Za-z0-9_-]{1,32}$/;

/** The first problem with the draft, in words; null when it can be saved. A new printer
 * needs an access code; an edit keeps the saved one when the box is empty. */
export function printerProblem(draft: PrinterDraft, isNew: boolean): string | null {
  if (!draft.name.trim()) return "Enter a name.";
  if (draft.name.trim().length > 100) return "Use a name of at most 100 characters.";
  if (!HOST.test(draft.host.trim()))
    return "Enter the printer's address: a host name or IP address, without http://.";
  const port = Number(draft.port.trim());
  if (!Number.isInteger(port) || port < 1 || port > 65535) return "Use a port from 1 to 65535.";
  if (!SERIAL.test(draft.serial.trim()))
    return "The serial uses letters, digits, - and _ (at most 32).";
  if (isNew && !draft.access_code) return "Enter the access code from the printer's screen.";
  if (draft.access_code.length > 64) return "The access code is at most 64 characters.";
  return null;
}

export function printerFields(draft: PrinterDraft): PrinterFields {
  return {
    name: draft.name.trim(),
    host: draft.host.trim(),
    port: Number(draft.port.trim()),
    serial: draft.serial.trim(),
    access_code: draft.access_code,
  };
}

/** Only what changed, so an edit leaves the rest (and an empty access code) alone. */
export function printerChanges(printer: PrinterOut, draft: PrinterDraft): Partial<PrinterFields> {
  const fields = printerFields(draft);
  const out: Partial<PrinterFields> = {};
  if (fields.name !== printer.name) out.name = fields.name;
  if (fields.host !== printer.host) out.host = fields.host;
  if (fields.port !== printer.port) out.port = fields.port;
  if (fields.serial !== printer.serial) out.serial = fields.serial;
  if (fields.access_code) out.access_code = fields.access_code;
  return out;
}

const TEST_RESULTS: Record<PrinterCheck, string> = {
  ok: "Connected. The printer accepted the access code.",
  unreachable: "Can't reach the printer. Check the address and port, and that it is on.",
  refused: "The printer refused the access code. Check it on the printer's screen.",
  pin_mismatch:
    "The printer presented a different certificate from the pinned one, so the access code was not sent.",
  error: "The printer answered with an error.",
};

export function testResultText(result: PrinterCheck): string {
  return TEST_RESULTS[result];
}

export function reportText(printer: PrinterOut, now: Date = new Date()): string {
  return printer.last_report_at
    ? `Last report ${ago(printer.last_report_at, now)}`
    : "No report yet";
}

/** The first 16 hex digits in groups of four, enough to compare by eye. */
export function shortFingerprint(sha256: string): string {
  return (
    sha256
      .slice(0, 16)
      .toUpperCase()
      .match(/.{1,4}/g)
      ?.join(" ") ?? ""
  );
}

/** Slots grouped by AMS unit, in order. */
export function byAms<T extends { ams_index: number }>(slots: T[]): { ams: number; slots: T[] }[] {
  const groups = new Map<number, T[]>();
  for (const slot of slots)
    groups.set(slot.ams_index, [...(groups.get(slot.ams_index) ?? []), slot]);
  return [...groups.entries()]
    .sort(([a], [b]) => a - b)
    .map(([ams, items]) => ({ ams, slots: items }));
}
