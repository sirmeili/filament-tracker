/** Helpers for showing printers and AMS slots. */

import type { AmsSlotRef, PrinterOut } from "#lib/api/types.ts";
import { ago } from "#lib/devices.ts";

/** "AMS 1, slot 2" from 0-based indexes. */
export function slotName(amsIndex: number, trayIndex: number): string {
  return `AMS ${amsIndex + 1}, slot ${trayIndex + 1}`;
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
  not_configured: "Not configured",
};

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
