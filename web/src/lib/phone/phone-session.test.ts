import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiUrl, setApiBase } from "#lib/api/client.ts";
import { browserBridge, setBridge } from "#lib/phone/bridge.ts";
import { scanEvent } from "#lib/phone/device-api.ts";
import { savePairing } from "#lib/phone/pairing-store.ts";
import { isPhonePath, pairingError, phone } from "#lib/phone/phone-state.svelte.ts";
import { BACKOFF_FIRST_MS } from "#lib/phone/queue.ts";
import { HEARTBEAT_MS, PhoneSession } from "#lib/phone/session.ts";
import {
  fakeBridge,
  fakeFetch,
  PAIRING,
  tagRead,
  type FakeBridge,
} from "../../test/fake-bridge.ts";

let native: FakeBridge;

beforeEach(() => {
  vi.useFakeTimers();
  native = fakeBridge();
  setBridge(native);
});

afterEach(async () => {
  setBridge(native);
  await phone.unpair();
  setBridge(browserBridge);
  setApiBase("");
  vi.useRealTimers();
});

const ok = () => ({ status: 200, body: {} });

describe("phone session", () => {
  it("needs a pairing and the salt", async () => {
    expect(await PhoneSession.open(native)).toBeNull();
    native.storage.set("pairing", JSON.stringify(PAIRING));
    expect(await PhoneSession.open(native)).toBeNull();
  });

  it("sends a heartbeat on start and every 5 minutes", async () => {
    await savePairing(PAIRING, "AA");
    const fetch = fakeFetch({ "POST /api/v1/devices/heartbeat": () => ({ status: 204 }) });
    const session = (await PhoneSession.open(native, fetch))!;

    session.start();
    await vi.advanceTimersByTimeAsync(0);
    expect(fetch.calls).toHaveLength(1);
    expect(JSON.parse(String(fetch.calls[0].init.body))).toEqual({
      fw_version: "app-test",
      queue_length: 0,
    });
    await vi.advanceTimersByTimeAsync(HEARTBEAT_MS);
    expect(fetch.calls).toHaveLength(2);
    session.stop();
    await vi.advanceTimersByTimeAsync(HEARTBEAT_MS);
    expect(fetch.calls).toHaveLength(2);
  });

  it("retries queued scans when they are due", async () => {
    await savePairing(PAIRING, "AA");
    let up = false;
    const fetch = fakeFetch({
      "POST /api/v1/devices/heartbeat": () => (up ? { status: 204 } : new TypeError("down")),
      "POST /api/v1/scans": () => (up ? ok() : new TypeError("down")),
    });
    const session = (await PhoneSession.open(native, fetch))!;
    await session.queue.add(scanEvent(PAIRING, tagRead(), "opened", "1"), Date.now());

    session.start();
    await vi.advanceTimersByTimeAsync(0);
    expect(session.queue.size).toBe(1); // the server is down: backed off

    up = true;
    await vi.advanceTimersByTimeAsync(BACKOFF_FIRST_MS);
    expect(session.queue.size).toBe(0);
    session.stop();
  });

  it("keeps the queue in secure storage", async () => {
    await savePairing(PAIRING, "AA");
    const session = (await PhoneSession.open(native, fakeFetch({})))!;
    await session.queue.add(scanEvent(PAIRING, tagRead(), "opened", "1"));

    expect(JSON.parse(native.storage.get("queue")!)).toHaveLength(1);
  });
});

describe("phone state", () => {
  it("pairs, points the API at the server and forgets", async () => {
    const fetch = fakeFetch({
      "GET /api/v1/devices/provisioning": () => ({ status: 200, body: { kdf_salt: "AABB" } }),
      "POST /api/v1/devices/heartbeat": () => ({ status: 204 }),
    });

    await phone.load(fetch);
    expect(phone.loaded).toBe(true);
    expect(phone.paired).toBe(false);

    await phone.pair(PAIRING, fetch);
    expect(phone.paired).toBe(true);
    expect(native.storage.get("kdf_salt")).toBe("AABB");
    expect(apiUrl("/me")).toBe("https://filament.example.com/api/v1/me");
    expect((fetch.calls[0].init.headers as Record<string, string>).Authorization).toBe(
      `Bearer ${PAIRING.token}`,
    );

    await phone.session!.queue.add(scanEvent(PAIRING, tagRead(), "opened", "1"));
    expect(phone.queueSize).toBe(1);

    await phone.unpair();
    expect(phone.paired).toBe(false);
    expect(apiUrl("/me")).toBe("/api/v1/me");
    expect(native.storage.has("pairing")).toBe(false);
  });

  it("does not load a session in a browser", async () => {
    setBridge(browserBridge);
    await phone.load();
    expect(phone.app).toBe(false);
    expect(phone.paired).toBe(false);
  });

  it("does not keep anything when the server refuses", async () => {
    const fetch = fakeFetch({ "GET /api/v1/devices/provisioning": () => ({ status: 401 }) });
    await expect(phone.pair(PAIRING, fetch)).rejects.toMatchObject({ status: 401 });
    expect(native.storage.size).toBe(0);
  });

  it("explains pairing failures", () => {
    expect(pairingError(new ApiError(0, ""))).toMatch(/Can't reach/);
    expect(pairingError(new ApiError(401, ""))).toMatch(/did not accept/);
    expect(pairingError(new ApiError(403, ""))).toMatch(/home network/);
    expect(pairingError(new ApiError(503, ""))).toMatch(/BAMBU_KDF_SALT/);
    expect(pairingError(new ApiError(500, ""))).toBe("Pairing failed. Try again.");
    expect(pairingError(new Error("x"))).toBe("Pairing failed. Try again.");
  });

  it("knows the phone-only pages", () => {
    expect(isPhonePath("/scan")).toBe(true);
    expect(isPhonePath("/pair")).toBe(true);
    expect(isPhonePath("/scanner")).toBe(false);
    expect(isPhonePath("/")).toBe(false);
  });
});

describe("online status", () => {
  it("follows the heartbeat and scans", async () => {
    await savePairing(PAIRING, "AA");
    let up = true;
    const fetch = fakeFetch({
      "POST /api/v1/devices/heartbeat": () => (up ? { status: 204 } : new TypeError("down")),
    });
    const session = (await PhoneSession.open(native, fetch))!;
    const seen: boolean[] = [];
    expect(session.online).toBeNull();

    session.subscribeOnline((online) => seen.push(online));
    await session.beat();
    up = false;
    await session.beat();
    await session.beat(); // no change, not repeated
    const late: boolean[] = [];
    const stop = session.subscribeOnline((online) => late.push(online));
    stop();

    expect(seen).toEqual([true, false]);
    expect(late).toEqual([false]); // told the current status at once
    session.stop();
  });

  it("counts a refused heartbeat as online", async () => {
    await savePairing(PAIRING, "AA");
    const fetch = fakeFetch({ "POST /api/v1/devices/heartbeat": () => ({ status: 401 }) });
    const session = (await PhoneSession.open(native, fetch))!;
    await session.beat();
    expect(session.online).toBe(true);
  });

  it("is shown on the phone state", async () => {
    await savePairing(PAIRING, "AA");
    vi.stubGlobal(
      "fetch",
      fakeFetch({ "POST /api/v1/devices/heartbeat": () => ({ status: 204 }) }),
    );
    await phone.load();
    await vi.advanceTimersByTimeAsync(0);
    expect(phone.online).toBe(true);
    await phone.unpair();
    expect(phone.online).toBeNull();
    vi.unstubAllGlobals();
  });
});
