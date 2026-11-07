/** A small client for the server's JSON API under /api/v1.
 *
 * The session cookie is sent automatically (same origin). Every request carries the
 * `X-Requested-With: filament-tracker` header, which the server requires on changes made
 * with the cookie and which pages on other sites cannot add.
 */

export const API_PREFIX = "/api/v1";
/** How long a page waits for the server before saying it cannot be reached. */
export const API_TIMEOUT_MS = 15_000;
export const CSRF_HEADER = { "X-Requested-With": "filament-tracker" } as const;

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
}

// In a browser the API is on the same site. In the phone app the pages come from the app
// itself, so requests go to the paired server's address instead (Capacitor's native HTTP
// keeps the session cookie for it).
let apiBase = "";

/** Send API requests to another server ("" for this site). */
export function setApiBase(url: string): void {
  apiBase = url.replace(/\/+$/, "");
}

export function apiUrl(path: string): string {
  return apiBase + API_PREFIX + path;
}

type Listener = () => void;
const unauthorizedListeners = new Set<Listener>();

/** Called when a request comes back 401: the session has ended or never existed. */
export function onUnauthorized(listener: Listener): () => void {
  unauthorizedListeners.add(listener);
  return () => unauthorizedListeners.delete(listener);
}

/** The message in a FastAPI error body: a string, or a list of validation errors. */
export function errorMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => (item && typeof item === "object" ? (item as { msg?: unknown }).msg : null))
        .filter((msg): msg is string => typeof msg === "string");
      if (messages.length) return messages.join("; ");
    }
  }
  return fallback;
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return undefined;
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

export async function api<T>(
  path: string,
  options: RequestOptions = {},
  fetchFn: typeof fetch = fetch,
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json", ...CSRF_HEADER };
  const init: RequestInit = {
    method: options.method ?? "GET",
    credentials: apiBase ? "include" : "same-origin",
    headers,
    signal: options.signal,
  };
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(options.body);
  }

  // A server that never answers (an address the phone cannot reach, a dropped
  // connection) would otherwise leave the page loading until the OS gives up. The timer
  // races the request because the phone's native HTTP may not honour the abort.
  const abort = new AbortController();
  init.signal = options.signal ? AbortSignal.any([options.signal, abort.signal]) : abort.signal;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      abort.abort();
      reject(new Error("timed out"));
    }, API_TIMEOUT_MS);
  });
  const answer = (async () => {
    const response = await fetchFn(apiUrl(path), init);
    return { response, body: await readJson(response) };
  })();
  let response: Response;
  let body: unknown;
  try {
    ({ response, body } = await Promise.race([answer, timeout]));
  } catch {
    throw new ApiError(0, "Cannot reach the server");
  } finally {
    clearTimeout(timer);
    answer.catch(() => {});
  }
  if (!response.ok) {
    if (response.status === 401) unauthorizedListeners.forEach((listener) => listener());
    throw new ApiError(response.status, errorMessage(body, `Request failed (${response.status})`));
  }
  return body as T;
}
