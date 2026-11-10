import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "#lib/api/client.ts";
import { Session } from "#lib/auth/session.svelte.ts";

const ALICE = { id: 1, username: "alice", role: "editor" };

function respond(...replies: Array<[number, unknown?]>) {
  const fetchFn = vi.fn();
  for (const [status, body] of replies) {
    fetchFn.mockResolvedValueOnce(
      new Response(body === undefined ? null : JSON.stringify(body), { status }),
    );
  }
  vi.stubGlobal("fetch", fetchFn);
  return fetchFn;
}

describe("Session", () => {
  let session: Session;
  beforeEach(() => {
    session = new Session();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("loads the signed-in user", async () => {
    respond([200, ALICE]);

    await session.load();

    expect(session.user).toEqual(ALICE);
    expect(session.loaded).toBe(true);
    expect(session.can("editor")).toBe(true);
    expect(session.can("admin")).toBe(false);
  });

  it.each([401, 403])("treats %i as signed out", async (status) => {
    respond([status, { detail: "no" }]);

    await session.load();

    expect(session.user).toBeNull();
    expect(session.loaded).toBe(true);
    expect(session.can("viewer")).toBe(false);
  });

  it("asks once more after a wait when told to, and finds the user then", async () => {
    vi.useFakeTimers();
    try {
      const fetchFn = respond([401, { detail: "no" }], [200, ALICE]);

      const loading = session.load(500);
      await vi.advanceTimersByTimeAsync(499);
      expect(fetchFn).toHaveBeenCalledTimes(1);
      await vi.advanceTimersByTimeAsync(1);
      await loading;

      expect(fetchFn).toHaveBeenCalledTimes(2);
      expect(session.user).toEqual(ALICE);
      expect(session.loaded).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });

  it("is signed out when the second answer is no too", async () => {
    const fetchFn = respond([401, { detail: "no" }], [401, { detail: "no" }]);

    await session.load(1);

    expect(fetchFn.mock.calls.filter(([url]) => url === "/api/v1/auth/me")).toHaveLength(2);
    expect(session.user).toBeNull();
    expect(session.loaded).toBe(true);
  });

  it("does not ask again when the server cannot be reached", async () => {
    const fetchFn = respond([500, { detail: "boom" }]);

    await expect(session.load(1)).rejects.toBeInstanceOf(ApiError);
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  it("passes other failures on, but still finishes loading", async () => {
    respond([500, { detail: "boom" }]);

    await expect(session.load()).rejects.toBeInstanceOf(ApiError);
    expect(session.loaded).toBe(true);
  });

  it("signs in", async () => {
    const fetchFn = respond([200, ALICE]);

    await session.login("alice", "secret password");

    expect(session.user).toEqual(ALICE);
    const init = fetchFn.mock.calls[0][1];
    expect(fetchFn.mock.calls[0][0]).toBe("/api/v1/auth/login");
    expect(JSON.parse(init.body)).toEqual({ username: "alice", password: "secret password" });
  });

  it("signs out, even if the request fails", async () => {
    respond([200, ALICE], [204]);
    await session.login("alice", "pw");
    await session.logout();
    expect(session.user).toBeNull();

    respond([200, ALICE], [500, { detail: "boom" }]);
    await session.login("alice", "pw");
    await expect(session.logout()).rejects.toBeInstanceOf(ApiError);
    expect(session.user).toBeNull();
  });

  it("notices when a signed-in session ends", async () => {
    respond([200, ALICE], [401, { detail: "Not signed in" }]);
    await session.load();

    await expect(session.load()).resolves.toBeUndefined();

    expect(session.user).toBeNull();
    expect(session.expired).toBe(true);
  });

  it("does not call a first visit an ended session", async () => {
    respond([401]);

    await session.load();

    expect(session.expired).toBe(false);
  });

  it("clears the ended flag on the next sign-in", async () => {
    respond([200, ALICE], [401], [404], [200, ALICE]);
    await session.load();
    await session.load();

    await session.login("alice", "pw");

    expect(session.expired).toBe(false);
  });

  it("finds an open setup when no one is signed in", async () => {
    const status = { open: true, time_zone_needed: true, kdf_salt_needed: false };
    const fetchFn = respond([401], [200, status]);

    await session.load();

    expect(fetchFn.mock.calls[1][0]).toContain("/setup");
    expect(session.setup).toEqual(status);
  });

  it.each([
    ["closed", [200, { open: false, time_zone_needed: false, kdf_salt_needed: false }]],
    ["hidden from outside the LAN", [404, { detail: "Not Found" }]],
    ["unreachable", [500, { detail: "down" }]],
  ] as const)("treats a setup that is %s as closed", async (_, reply) => {
    respond([401], [...reply]);

    await session.load();

    expect(session.setup).toBeNull();
    expect(session.loaded).toBe(true);
  });

  it("finishing setup signs the new admin in", async () => {
    const admin = { id: 1, username: "frank", role: "admin", time_zone: "UTC" };
    respond([401], [200, { open: true, time_zone_needed: false, kdf_salt_needed: false }]);
    await session.load();
    const fetchFn = respond([201, admin]);

    await session.finishSetup({ code: "AAAA", username: "frank", password: "x".repeat(12) });

    expect(fetchFn.mock.calls[0][1].method).toBe("POST");
    expect(session.user).toEqual(admin);
    expect(session.setup).toBeNull();
  });
});
