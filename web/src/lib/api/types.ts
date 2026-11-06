import type { Role } from "#lib/roles.ts";

/** The signed-in user (`GET /auth/me`). */
export interface Me {
  id: number;
  username: string;
  role: Role;
}

/** Response bodies from server/src/filament_tracker/api/read_schemas.py. */

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Product {
  id: number;
  display_name: string;
  filament_type: string;
  /** RRGGBBAA */
  color_rgba: string;
  material_id: string | null;
  variant_id: string | null;
  low_stock_threshold: number;
  nearly_out_pct: number;
  provisional: boolean;
}

export interface Counts {
  sealed: number;
  open: number;
  empty: number;
  unknown: number;
}

export interface OpenSpool {
  id: number;
  remaining_pct: number | null;
  nearly_out: boolean;
}

/** One inventory card. */
export interface ProductSummary {
  product: Product;
  counts: Counts;
  low_stock: boolean;
  open_spools: OpenSpool[];
}

export type SpoolState = "sealed" | "open" | "empty" | "unknown";

export interface SpoolRow {
  id: number;
  state: SpoolState;
  product: Product;
  placeholder: boolean;
  location: string | null;
  remaining_pct: number | null;
  received_at: string | null;
  opened_at: string | null;
  emptied_at: string | null;
}

export interface TagOut {
  uid: string;
  first_seen_at: string;
  decoded: Record<string, unknown> | null;
  decoder_version: number | null;
}

export interface EventOut {
  id: string;
  spool_id: number;
  product_name: string;
  color_rgba: string;
  type: "received" | "opened" | "empty" | "revert" | string;
  source: string;
  occurred_at: string;
  recorded_at: string;
  flagged: boolean;
  device_id: string | null;
  device_name: string | null;
  username: string | null;
  reverts: string | null;
  reverted_by: string | null;
  can_undo: boolean;
  reviewed_at: string | null;
  reviewed_by: string | null;
}

export interface SpoolDetail extends SpoolRow {
  notes: string | null;
  spool_weight_g: number | null;
  grams_left: number | null;
  tags: TagOut[];
  /** Newest first */
  events: EventOut[];
}

export interface ReviewOut {
  flagged_events: EventOut[];
  unidentified_tags: { uid: string }[];
  likely_empty: SpoolRow[];
}

export type ManualAction = "received" | "opened" | "empty";

export interface ActionResult {
  outcome: "applied" | "already_in_state" | "flagged";
  event: EventOut;
  spool: SpoolDetail;
}
