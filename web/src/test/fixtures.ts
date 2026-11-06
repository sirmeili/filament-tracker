/** Made-up API data for the unit tests. */

import type {
  EventOut,
  Product,
  ProductSummary,
  SpoolDetail,
  SpoolRow,
  TagOut,
} from "#lib/api/types.ts";

export function product(overrides: Partial<Product> = {}): Product {
  return {
    id: 1,
    display_name: "Black PLA Basic",
    filament_type: "PLA",
    color_rgba: "000000FF",
    material_id: "GFA00",
    variant_id: "A00-K00",
    low_stock_threshold: 2,
    nearly_out_pct: 15,
    provisional: false,
    ...overrides,
  };
}

export function summary(overrides: Partial<ProductSummary> = {}): ProductSummary {
  return {
    product: product(),
    counts: { sealed: 1, open: 1, empty: 3, unknown: 0 },
    low_stock: true,
    open_spools: [{ id: 3, remaining_pct: 12, nearly_out: true }],
    ...overrides,
  };
}

export function spoolRow(overrides: Partial<SpoolRow> = {}): SpoolRow {
  return {
    id: 1,
    state: "open",
    product: product(),
    placeholder: false,
    location: "Shelf A",
    remaining_pct: 62,
    received_at: "2026-10-12T16:05:00Z",
    opened_at: "2026-10-20T18:41:00Z",
    emptied_at: null,
    ...overrides,
  };
}

export function event(overrides: Partial<EventOut> = {}): EventOut {
  return {
    id: "e1",
    spool_id: 1,
    product_name: "Black PLA Basic",
    color_rgba: "000000FF",
    type: "received",
    source: "scanner",
    occurred_at: "2026-10-12T16:05:00Z",
    recorded_at: "2026-10-12T16:05:00Z",
    flagged: false,
    device_id: "scanner-1",
    device_name: "Workbench scanner",
    username: null,
    reverts: null,
    reverted_by: null,
    can_undo: true,
    reviewed_at: null,
    reviewed_by: null,
    ...overrides,
  };
}

export function tag(overrides: Partial<TagOut> = {}): TagOut {
  return {
    uid: "A1B2C3D4",
    first_seen_at: "2026-10-12T16:05:00Z",
    decoded: {
      material_id: "GFA00",
      variant_id: "A00-K00",
      filament_type: "PLA",
      detailed_filament_type: "PLA Basic",
      filament_diameter_mm: 1.75,
      spool_weight_g: 1000,
      production_date: "2026-09-18T00:00:00",
    },
    decoder_version: 1,
    ...overrides,
  };
}

export function spoolDetail(overrides: Partial<SpoolDetail> = {}): SpoolDetail {
  return {
    ...spoolRow(),
    notes: "Dried 8 h",
    spool_weight_g: 1000,
    grams_left: 620,
    tags: [tag()],
    events: [
      event({ id: "e2", type: "opened", occurred_at: "2026-10-20T18:41:00Z" }),
      event({ can_undo: true }),
    ],
    ...overrides,
  };
}

/** A fetch stand-in answering each request from `routes` ("METHOD /path" → body). */
export function fakeFetch(
  routes: Record<string, unknown | ((body: unknown) => unknown)>,
): typeof fetch & { calls: { method: string; path: string; body: unknown }[] } {
  const calls: { method: string; path: string; body: unknown }[] = [];
  const fn = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input).replace("/api/v1", "");
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, path, body });
    const key = `${method} ${path}`;
    if (!(key in routes))
      return new Response(JSON.stringify({ detail: "no route" }), { status: 404 });
    const answer = routes[key];
    const value = typeof answer === "function" ? answer(body) : answer;
    if (value instanceof Response) return value;
    return new Response(JSON.stringify(value), { status: 200 });
  }) as typeof fetch & { calls: typeof calls };
  fn.calls = calls;
  return fn;
}
