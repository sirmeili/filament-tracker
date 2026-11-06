import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "#lib/api/client.ts";
import { checkPairing, parsePairing } from "#lib/pairing.ts";
import { browserBridge, bridge, setBridge } from "#lib/phone/bridge.ts";
import { NFC_MESSAGES, stateText } from "#lib/phone/card-text.ts";
import { DeviceApi, isOffline, REQUEST_TIMEOUT_MS, scanEvent } from "#lib/phone/device-api.ts";
import { forgetPairing, loadPairing, loadSalt, savePairing } from "#lib/phone/pairing-store.ts";
import { backoff, BACKOFF_MAX_MS, OfflineQueue, QUEUE_LIMIT } from "#lib/phone/queue.ts";
import type { Card } from "#lib/phone/scan-flow.ts";
import { decodeOffline, offlineName } from "#lib/phone/tag-decode.ts";
import {
  fakeBridge,
  fakeFetch,
  PAIRING,
  tagRead,
  type FakeBridge,
} from "../../test/fake-bridge.ts";
import tags from "../../test/tags.json";

let native: FakeBridge;

beforeEach(() => {
  native = fakeBridge();
  setBridge(native);
});

afterEach(() => setBridge(browserBridge));

describe("offline decode", () => {
  it.each(tags)("matches the server's decoder: $name", ({ blocks, expected }) => {
    expect(decodeOffline(blocks)).toEqual(expected);
  });

  it("refuses blocks that are not a tag", () => {
    expect(decodeOffline([])).toBeNull();
    expect(decodeOffline(Array(48).fill("zz"))).toBeNull();
  });

  it("names a spool as the server names a new product", () => {
    const [black, , untyped] = tags;
    expect(offlineName(decodeOffline(black.blocks)!)).toBe("PLA Basic #000000");
    expect(offlineName(decodeOffline(untyped.blocks)!)).toBe("PLA #FF6A13");
  });
});

describe("pairing codes", () => {
  const code = (fields: Record<string, unknown>) =>
    JSON.stringify({
      v: 1,
      url: PAIRING.url,
      token: PAIRING.token,
      device_id: "phone-1",
      ...fields,
    });

  it("reads a code from the Devices page", () => {
    expect(parsePairing(code({ url: "https://filament.example.com/" }))).toEqual({
      pairing: PAIRING,
    });
  });

  it.each([
    ["not json", /not a Filament Tracker/],
    ["7", /not a Filament Tracker/],
    [JSON.stringify({ v: 2 }), /different version/],
    [JSON.stringify({ v: 1, url: "https://x" }), /incomplete/],
    ["{}", /different version/],
  ])("refuses %s", (text, message) => {
    expect(parsePairing(text)).toEqual({ error: expect.stringMatching(message) });
  });

  it("checks typed details", () => {
    expect(checkPairing("nope", PAIRING.token, "phone-1")).toEqual({
      error: expect.stringMatching(/full address/),
    });
    expect(checkPairing(PAIRING.url, "secret", "phone-1")).toEqual({
      error: expect.stringMatching(/ftd_/),
    });
    expect(checkPairing(PAIRING.url, PAIRING.token, "Phone 1")).toEqual({
      error: expect.stringMatching(/lower-case/),
    });
    expect(checkPairing(` ${PAIRING.url} `, ` ${PAIRING.token} `, " phone-1 ")).toEqual({
      pairing: PAIRING,
    });
  });
});

describe("bridge and storage", () => {
  it("is not the app in a browser", async () => {
    setBridge(browserBridge);
    expect(bridge().app).toBe(false);
    expect(await browserBridge.nfcStatus()).toBe("no_nfc");
    await expect(browserBridge.scanQr()).rejects.toThrow(/Android app/);
  });

  it("keeps the pairing and salt in secure storage", async () => {
    expect(await loadPairing()).toBeNull();
    await savePairing(PAIRING, "AABB");

    expect(await loadPairing()).toEqual(PAIRING);
    expect(await loadSalt()).toBe("AABB");
    await forgetPairing();
    expect(native.storage.size).toBe(0);
  });

  it("treats unreadable pairing data as not paired", async () => {
    native.storage.set("pairing", "{");
    expect(await loadPairing()).toBeNull();
    native.storage.set("pairing", JSON.stringify({ url: 1 }));
    expect(await loadPairing()).toBeNull();
  });
});

describe("device API", () => {
  it("sends scans with the device token to the paired server", async () => {
    const fetch = fakeFetch({
      "POST /api/v1/scans": () => ({ status: 200, body: { feedback: "ok" } }),
    });
    const at = new Date("2026-11-06T10:00:00Z");
    const event = scanEvent(PAIRING, tagRead(), "opened", "1.0", at, "id-1");

    expect(await new DeviceApi(PAIRING, fetch).scan(event)).toEqual({ feedback: "ok" });

    const { url, init } = fetch.calls[0];
    expect(url).toBe("https://filament.example.com/api/v1/scans");
    expect((init.headers as Record<string, string>).Authorization).toBe(`Bearer ${PAIRING.token}`);
    expect(init.credentials).toBe("omit");
    expect(JSON.parse(String(init.body))).toMatchObject({
      event_id: "id-1",
      device_id: "phone-1",
      action: "opened",
      tag_uid: "01020304",
      scanned_at: "2026-11-06T10:00:00.000Z",
      fw_version: "1.0",
    });
  });

  it("reverts, sends heartbeats and fetches the salt", async () => {
    const fetch = fakeFetch({
      "POST /api/v1/events/": () => ({ status: 200, body: {} }),
      "POST /api/v1/devices/heartbeat": () => ({ status: 204 }),
      "GET /api/v1/devices/provisioning": () => ({ status: 200, body: { kdf_salt: "AA" } }),
    });
    const api = new DeviceApi(PAIRING, fetch);

    await api.revert("a/b");
    await api.heartbeat("1.0", 3);
    expect(await api.provisioning()).toBe("AA");
    expect(fetch.calls[0].url).toMatch(/events\/a%2Fb\/revert$/);
    expect(JSON.parse(String(fetch.calls[1].init.body))).toEqual({
      fw_version: "1.0",
      queue_length: 3,
    });
  });

  it("turns failures into API errors", async () => {
    const api = new DeviceApi(
      PAIRING,
      fakeFetch({
        "POST /api/v1/scans": () => new TypeError("network down"),
        "GET /api/v1/devices/provisioning": () => ({ status: 503, body: { detail: "no salt" } }),
        "POST /api/v1/devices/heartbeat": () => ({ status: 500 }),
      }),
    );

    await expect(api.scan(scanEvent(PAIRING, tagRead(), "lookup", "1"))).rejects.toMatchObject({
      status: 0,
    });
    await expect(api.provisioning()).rejects.toMatchObject({ status: 503, message: "no salt" });
    await expect(api.heartbeat("1", 0)).rejects.toMatchObject({ status: 500 });
  });

  it("gives up on a server that never answers", async () => {
    vi.useFakeTimers();
    let signal: AbortSignal | undefined;
    const hang = ((_url: RequestInfo | URL, init?: RequestInit) => {
      signal = init?.signal ?? undefined;
      return new Promise<Response>(() => {});
    }) as typeof globalThis.fetch;

    const lookup = new DeviceApi(PAIRING, hang).scan(scanEvent(PAIRING, tagRead(), "lookup", "1"));
    const settled = expect(lookup).rejects.toMatchObject({ status: 0 });
    await vi.advanceTimersByTimeAsync(REQUEST_TIMEOUT_MS - 1);
    expect(signal?.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    await settled;
    expect(signal?.aborted).toBe(true);
    vi.useRealTimers();
  });

  it("gives up on an answer whose body never arrives", async () => {
    vi.useFakeTimers();
    const slowBody = (async () =>
      ({
        ok: true,
        status: 200,
        text: () => new Promise<string>(() => {}),
      }) as Response) as typeof globalThis.fetch;

    const heartbeat = new DeviceApi(PAIRING, slowBody).heartbeat("1", 0);
    const settled = expect(heartbeat).rejects.toMatchObject({ status: 0 });
    await vi.advanceTimersByTimeAsync(REQUEST_TIMEOUT_MS);
    await settled;
    vi.useRealTimers();
  });

  it("reads non-JSON error bodies", async () => {
    const fetch = (async () => new Response("<html>", { status: 502 })) as typeof globalThis.fetch;
    await expect(new DeviceApi(PAIRING, fetch).provisioning()).rejects.toMatchObject({
      status: 502,
      message: "Request failed (502)",
    });
  });

  it("knows which errors are worth retrying", () => {
    expect(isOffline(new ApiError(0, "x"))).toBe(true);
    expect(isOffline(new ApiError(503, "x"))).toBe(true);
    expect(isOffline(new ApiError(401, "x"))).toBe(false);
    expect(isOffline(new Error("x"))).toBe(false);
  });
});

describe("offline queue", () => {
  function store(initial: string | null = null) {
    let text = initial;
    return {
      load: vi.fn(async () => text),
      save: vi.fn(async (next: string) => void (text = next)),
      get text() {
        return text;
      },
    };
  }
  const event = (id: string) => scanEvent(PAIRING, tagRead(), "opened", "1", new Date(0), id);

  it("backs off from 5 seconds to at most 5 minutes", () => {
    expect([1, 2, 3].map(backoff)).toEqual([5_000, 10_000, 20_000]);
    expect(backoff(0)).toBe(5_000);
    expect(backoff(20)).toBe(BACKOFF_MAX_MS);
  });

  it("keeps events until they are delivered", async () => {
    const saved = store();
    const queue = await OfflineQueue.open(saved);
    const sizes: number[] = [];
    queue.subscribe((size) => sizes.push(size));
    await queue.add(event("a"), 0);
    await queue.add(event("b"), 0);

    const offline = vi.fn().mockRejectedValue(new ApiError(0, "down"));
    expect(await queue.flush(offline, 0)).toEqual({ sent: 0, refused: 0, waiting: 2 });
    expect(offline).toHaveBeenCalledTimes(1); // stops at the first unreachable one
    expect(queue.nextDue()).toBe(0); // b was not tried

    const reopened = await OfflineQueue.open(store(saved.text));
    expect(reopened.size).toBe(2);

    const send = vi
      .fn()
      .mockResolvedValueOnce({})
      .mockRejectedValueOnce(new ApiError(401, "revoked"));
    expect(await queue.flush(send, 10_000)).toEqual({ sent: 1, refused: 1, waiting: 0 });
    expect(queue.size).toBe(0);
    expect(queue.nextDue()).toBeNull();
    expect(sizes).toEqual([1, 2, 2, 0]);
  });

  it("waits for the backoff before retrying", async () => {
    const queue = await OfflineQueue.open(store());
    await queue.add(event("a"), 0);
    await queue.flush(() => Promise.reject(new Error("boom")), 0);

    const send = vi.fn().mockResolvedValue({});
    await queue.flush(send, 4_999);
    expect(send).not.toHaveBeenCalled();
    expect(queue.nextDue()).toBe(5_000);
    await queue.flush(send, 5_000);
    expect(send).toHaveBeenCalledTimes(1);
  });

  it("holds at least 50 and refuses more than its limit", async () => {
    const queue = await OfflineQueue.open(store());
    expect(QUEUE_LIMIT).toBeGreaterThanOrEqual(50);
    for (let i = 0; i < QUEUE_LIMIT; i++) expect(await queue.add(event(`e${i}`))).toBe(true);
    expect(await queue.add(event("over"))).toBe(false);
  });

  it("can take an event back out", async () => {
    const queue = await OfflineQueue.open(store());
    await queue.add(event("a"));
    expect(await queue.remove("b")).toBe(false);
    expect(await queue.remove("a")).toBe(true);
    expect(queue.size).toBe(0);
  });

  it("drops a corrupt queue", async () => {
    expect((await OfflineQueue.open(store("{"))).size).toBe(0);
    expect((await OfflineQueue.open(store('{"a":1}'))).size).toBe(0);
    expect((await OfflineQueue.open(store('[null,{"x":1}]'))).size).toBe(0);
  });
});

describe("card text", () => {
  const card = (fields: Partial<Card>): Card => ({
    name: "PLA Basic",
    colorRgba: null,
    state: "sealed",
    receivedAt: "2026-10-12T10:00:00Z",
    openedAt: "2026-10-20T10:00:00Z",
    emptiedAt: "2026-11-01T10:00:00Z",
    remainingPct: null,
    spoolId: 1,
    placeholder: false,
    offline: false,
    ...fields,
  });
  const now = new Date("2026-11-06T10:00:00Z");

  it("says the state with its date", () => {
    expect(stateText(card({}), now)).toBe("Sealed, received Oct 12");
    expect(stateText(card({ state: "open" }), now)).toBe("Open, opened Oct 20");
    expect(stateText(card({ state: "empty" }), now)).toBe("Empty, used up Nov 1");
    expect(stateText(card({ state: null }), now)).toBe("Not tracked yet");
    expect(stateText(card({ state: "unknown" }), now)).toBe("State unknown");
    expect(stateText(card({ placeholder: true }), now)).toBe("Added by hand, received Oct 12");
    expect(stateText(card({ offline: true }), now)).toMatch(/Offline/);
    expect(stateText(card({}))).toMatch(/^Sealed, received Oct 12/);
  });

  it("explains each NFC problem", () => {
    expect(Object.keys(NFC_MESSAGES).sort()).toEqual(["nfc_off", "no_mifare", "no_nfc"]);
  });
});

describe("scan card", async () => {
  const { render, screen } = await import("@testing-library/svelte");
  const ScanCard = (await import("#lib/components/phone/ScanCard.svelte")).default;
  const ActionKeys = (await import("#lib/components/phone/ActionKeys.svelte")).default;

  it("shows a spool with no swatch, no link and the AMS remaining", () => {
    render(ScanCard, {
      card: {
        name: "PLA Basic #000000",
        colorRgba: null,
        state: "open",
        receivedAt: null,
        openedAt: "2026-10-20T10:00:00Z",
        emptiedAt: null,
        remainingPct: 40,
        spoolId: null,
        placeholder: false,
        offline: false,
      },
    });

    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByText("40% left, as the AMS last reported")).toBeInTheDocument();
  });

  it("leaves a blank slot for a missing action and no hint without a suggestion", () => {
    const { container } = render(ActionKeys, {
      actions: ["opened", null, "cancel"],
      suggested: null,
      busy: true,
      onchoose: vi.fn(),
    });

    expect(screen.getAllByRole("button")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Opened" })).toBeDisabled();
    expect(container.querySelectorAll(".keys > span")).toHaveLength(1);
    expect(screen.queryByText(/suggested action/)).toBeNull();
  });
});
