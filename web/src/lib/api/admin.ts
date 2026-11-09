/** Calls behind the Review, Activity, Devices, Users and Account pages, and manual entry. */

import { api } from "#lib/api/client.ts";
import type {
  DeviceCreated,
  DeviceOut,
  EventOut,
  EventSource,
  Page,
  PrinterOut,
  Product,
  ReviewOut,
  SpoolDetail,
  UserOut,
} from "#lib/api/types.ts";
import type { Role } from "#lib/roles.ts";

// --- Review -----------------------------------------------------------------------------

export function getReview(): Promise<ReviewOut> {
  return api<ReviewOut>("/review");
}

export function acceptEvent(id: string): Promise<EventOut> {
  return api<EventOut>(`/review/events/${id}/accept`, { method: "POST" });
}

export function unacceptEvent(id: string): Promise<EventOut> {
  return api<EventOut>(`/review/events/${id}/unaccept`, { method: "POST" });
}

export function dismissTag(uid: string): Promise<void> {
  return api<void>(`/review/tags/${encodeURIComponent(uid)}/dismiss`, { method: "POST" });
}

export function restoreTag(uid: string): Promise<void> {
  return api<void>(`/review/tags/${encodeURIComponent(uid)}/restore`, { method: "POST" });
}

export function dismissLikelyEmpty(spoolId: number): Promise<void> {
  return api<void>(`/review/spools/${spoolId}/dismiss`, { method: "POST" });
}

export function restoreLikelyEmpty(spoolId: number): Promise<void> {
  return api<void>(`/review/spools/${spoolId}/restore`, { method: "POST" });
}

// --- Activity ---------------------------------------------------------------------------

export function listEvents(query: {
  source?: EventSource;
  limit: number;
  offset: number;
}): Promise<Page<EventOut>> {
  const params = new URLSearchParams({ limit: String(query.limit), offset: String(query.offset) });
  if (query.source) params.set("source", query.source);
  return api<Page<EventOut>>(`/events?${params}`);
}

// --- Manual entry -----------------------------------------------------------------------

export function listProducts(): Promise<Product[]> {
  return api<Product[]>("/products");
}

export function createProduct(body: {
  display_name: string;
  filament_type: string;
  color_rgba: string;
}): Promise<Product> {
  return api<Product>("/products", { method: "POST", body });
}

export function addSpool(body: {
  product_id: number;
  location: string | null;
  notes: string | null;
}): Promise<SpoolDetail> {
  return api<SpoolDetail>("/spools", { method: "POST", body });
}

// --- Devices ----------------------------------------------------------------------------

export function listDevices(): Promise<DeviceOut[]> {
  return api<DeviceOut[]>("/devices");
}

export function registerDevice(id: string, name: string): Promise<DeviceCreated> {
  return api<DeviceCreated>("/devices", { method: "POST", body: { id, name } });
}

export function rotateToken(id: string): Promise<DeviceCreated> {
  return api<DeviceCreated>(`/devices/${encodeURIComponent(id)}/rotate`, { method: "POST" });
}

export function revokeDevice(id: string): Promise<void> {
  return api<void>(`/devices/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export function listPrinters(): Promise<PrinterOut[]> {
  return api<PrinterOut[]>("/printers");
}

export function unpinPrinter(id: number): Promise<PrinterOut> {
  return api<PrinterOut>(`/printers/${id}/unpin`, { method: "POST" });
}

export interface PrinterFields {
  name: string;
  host: string;
  port: number;
  serial: string;
  access_code: string;
}

export type PrinterCheck = "ok" | "unreachable" | "refused" | "pin_mismatch" | "error";

export function addPrinter(fields: PrinterFields): Promise<PrinterOut> {
  return api<PrinterOut>("/printers", { method: "POST", body: fields });
}

/** Change only the fields given; without an access code the saved one is kept. */
export function editPrinter(id: number, changes: Partial<PrinterFields>): Promise<PrinterOut> {
  return api<PrinterOut>(`/printers/${id}`, { method: "PATCH", body: changes });
}

export function removePrinter(id: number): Promise<void> {
  return api<void>(`/printers/${id}`, { method: "DELETE" });
}

/** Connect once with the saved values and any entered ones, without saving. */
export function testPrinter(
  id: number,
  values: Partial<Pick<PrinterFields, "host" | "port" | "access_code">>,
): Promise<{ result: PrinterCheck }> {
  return api<{ result: PrinterCheck }>(`/printers/${id}/test`, { method: "POST", body: values });
}

// --- Users and account ------------------------------------------------------------------

export function listUsers(): Promise<UserOut[]> {
  return api<UserOut[]>("/users");
}

export function createUser(username: string, role: Role, password: string): Promise<UserOut> {
  return api<UserOut>("/users", { method: "POST", body: { username, role, password } });
}

export function updateUser(
  id: number,
  changes: { role?: Role; disabled?: boolean; password?: string },
): Promise<UserOut> {
  return api<UserOut>(`/users/${id}`, { method: "PATCH", body: changes });
}

export function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  return api<void>("/auth/password", {
    method: "POST",
    body: { current_password: currentPassword, new_password: newPassword },
  });
}
