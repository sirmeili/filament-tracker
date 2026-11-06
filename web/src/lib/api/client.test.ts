import { afterEach, describe, expect, it, vi } from "vitest";
import {
  api,
  ApiError,
  apiUrl,
  errorMessage,
  onUnauthorized,
  setApiBase,
} from "#lib/api/client.ts";

function reply(status: number, body?: unknown): Response {
  const text = body === undefined ? "" : typeof body === "string" ? body : JSON.stringify(body);
  return new Response(status === 204 ? null : text, { status });
}

describe("api", () => {
  const unsubscribe: Array<() => void> = [];
  afterEach(() => unsubscribe.splice(0).forEach((stop) => stop()));

  it("sends the CSRF header and the cookie on every request", async () => {
    const fetchFn = vi.fn().mockResolvedValue(reply(200, { ok: true }));

    const result = await api<{ ok: boolean }>("/auth/me", {}, fetchFn);

    expect(result).toEqual({ ok: true });
    const [url, init] = fetchFn.mock.calls[0];
    expect(url).toBe("/api/v1/auth/me");
    expect(init.method).toBe("GET");
    expect(init.credentials).toBe("same-origin");
    expect(init.headers["X-Requested-With"]).toBe("filament-tracker");
    expect(init.body).toBeUndefined();
  });

  it("sends a JSON body", async () => {
    const fetchFn = vi.fn().mockResolvedValue(reply(204));

    const result = await api("/auth/logout", { method: "POST", body: { a: 1 } }, fetchFn);

    expect(result).toBeUndefined();
    const init = fetchFn.mock.calls[0][1];
    expect(init.method).toBe("POST");
    expect(init.body).toBe('{"a":1}');
    expect(init.headers["Content-Type"]).toBe("application/json");
  });

  it("turns error replies into ApiError with the server's message", async () => {
    const fetchFn = vi.fn().mockResolvedValue(reply(409, { detail: "already exists" }));

    const error = await api("/x", {}, fetchFn).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 409, message: "already exists" });
  });

  it("falls back to a generic message when the body is not JSON", async () => {
    const fetchFn = vi.fn().mockResolvedValue(reply(502, "<html>Bad gateway</html>"));

    await expect(api("/x", {}, fetchFn)).rejects.toMatchObject({
      status: 502,
      message: "Request failed (502)",
    });
  });

  it("reports a network failure as status 0", async () => {
    const fetchFn = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(api("/x", {}, fetchFn)).rejects.toMatchObject({
      status: 0,
      message: "Cannot reach the server",
    });
  });

  it("tells listeners when a request is unauthorized", async () => {
    const listener = vi.fn();
    unsubscribe.push(onUnauthorized(listener));
    const fetchFn = vi.fn().mockResolvedValue(reply(401, { detail: "Not signed in" }));

    await expect(api("/x", {}, fetchFn)).rejects.toBeInstanceOf(ApiError);
    expect(listener).toHaveBeenCalledOnce();
  });

  it("stops telling a listener once unsubscribed", async () => {
    const listener = vi.fn();
    onUnauthorized(listener)();
    const fetchFn = vi.fn().mockResolvedValue(reply(401));

    await expect(api("/x", {}, fetchFn)).rejects.toBeInstanceOf(ApiError);
    expect(listener).not.toHaveBeenCalled();
  });

  it("uses the global fetch by default", async () => {
    const fetchFn = vi.fn().mockResolvedValue(reply(200, []));
    vi.stubGlobal("fetch", fetchFn);
    try {
      await api("/x");
      expect(fetchFn).toHaveBeenCalledOnce();
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

describe("errorMessage", () => {
  it("joins validation errors", () => {
    const body = { detail: [{ msg: "too short" }, { msg: "required" }, "odd", null] };
    expect(errorMessage(body, "x")).toBe("too short; required");
  });

  it.each([null, "text", {}, { detail: 5 }, { detail: [{}] }])("falls back for %j", (body) => {
    expect(errorMessage(body, "fallback")).toBe("fallback");
  });
});

describe("api in the phone app", () => {
  afterEach(() => setApiBase(""));

  it("sends requests, with the session cookie, to the paired server", async () => {
    const fetchFn = vi.fn(async () => new Response("{}", { status: 200 }));
    setApiBase("https://filament.example.com/");

    await api("/me", {}, fetchFn as unknown as typeof fetch);

    expect(apiUrl("/me")).toBe("https://filament.example.com/api/v1/me");
    expect(fetchFn).toHaveBeenCalledWith(
      "https://filament.example.com/api/v1/me",
      expect.objectContaining({ credentials: "include" }),
    );
  });
});
