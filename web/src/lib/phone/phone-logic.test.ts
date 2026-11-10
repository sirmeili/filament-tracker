import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "#lib/api/client.ts";
import { checkPairing, parsePairing } from "#lib/pairing.ts";
import { browserBridge, bridge, setBridge } from "#lib/phone/bridge.ts";
import { cardLine, chipKind, chipText, NFC_MESSAGES } from "#lib/phone/card-text.ts";
import { DeviceApi, isOffline, REQUEST_TIMEOUT_MS, scanEvent } from "#lib/phone/device-api.ts";
import { forgetPairing, loadPairing, loadSalt, savePairing } from "#lib/phone/pairing-store.ts";
import { backoff, BACKOFF_MAX_MS, OfflineQueue, QUEUE_LIMIT } from "#lib/phone/queue.ts";
import type { Card, FlowView, LastScan } from "#lib/phone/scan-flow.ts";
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
    ["not json", /not a RollCall/],
    ["7", /not a RollCall/],
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
    expect(await api.provisioning()).toEqual({ salt: "AA", access: null });
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

  it("counts a page that is not the server's JSON as not reaching it", async () => {
    for (const status of [502, 200, 403]) {
      const fetch = (async () => new Response("<html>", { status })) as typeof globalThis.fetch;
      await expect(new DeviceApi(PAIRING, fetch).provisioning()).rejects.toMatchObject({
        status: 0,
        message: "Cannot reach the server",
      });
    }
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

  it("says the state with its date and the spool number", () => {
    expect(cardLine(card({}), now)).toBe("Received Oct 12 · #1");
    expect(cardLine(card({ state: "open" }), now)).toBe("Opened Oct 20 · #1");
    expect(cardLine(card({ state: "empty" }), now)).toBe("Used up Nov 1 · #1");
    expect(cardLine(card({ state: null, spoolId: null }), now)).toBe("New tag");
    expect(cardLine(card({ state: "unknown" }), now)).toBe("State unknown · #1");
    expect(cardLine(card({ placeholder: true }), now)).toBe("Added by hand, received Oct 12 · #1");
    expect(cardLine(card({ offline: true }), now)).toMatch(/queued/);
    expect(cardLine(card({ spoolId: null }))).toBe("Received Oct 12");
  });

  it("labels the state chip", () => {
    expect([chipText(card({})), chipKind(card({}))]).toEqual(["Sealed", "sealed"]);
    expect([chipText(card({ state: "empty" })), chipKind(card({ state: "empty" }))]).toEqual([
      "Used up",
      "empty",
    ]);
    expect([chipText(card({ state: null })), chipKind(card({ state: null }))]).toEqual([
      "Not tracked yet",
      "new",
    ]);
    expect([chipText(card({ offline: true })), chipKind(card({ offline: true }))]).toEqual([
      "Offline",
      "new",
    ]);
    expect([chipText(card({ state: "odd" })), chipKind(card({ state: "odd" }))]).toEqual([
      "Unknown",
      "unknown",
    ]);
  });

  it("explains each NFC problem", () => {
    expect(Object.keys(NFC_MESSAGES).sort()).toEqual(["nfc_off", "no_mifare", "no_nfc"]);
  });
});

describe("scan screen parts", async () => {
  const { render, screen } = await import("@testing-library/svelte");
  const ScanCard = (await import("#lib/components/phone/ScanCard.svelte")).default;
  const ActionKeys = (await import("#lib/components/phone/ActionKeys.svelte")).default;
  const ScanResult = (await import("#lib/components/phone/ScanResult.svelte")).default;
  const ScanHeader = (await import("#lib/components/phone/ScanHeader.svelte")).default;
  const { Theme } = await import("#lib/theme.svelte.ts");

  const spool: Card = {
    name: "PLA Basic #000000",
    colorRgba: null,
    state: "open",
    receivedAt: null,
    openedAt: "2026-10-20T10:00:00Z",
    emptiedAt: null,
    remainingPct: 40,
    spoolId: 7,
    placeholder: false,
    offline: false,
  };
  const view = (fields: Partial<FlowView>): FlowView => ({
    phase: "result",
    outcome: "notice",
    countdown: null,
    card: spool,
    actions: [],
    suggested: null,
    message: null,
    tone: "ok",
    last: null,
    ...fields,
  });
  const last = (fields: Partial<LastScan> = {}): LastScan => ({
    card: spool,
    tagUid: "AA",
    action: "opened",
    eventId: "e1",
    at: 0,
    queued: false,
    undone: false,
    ...fields,
  });
  const handlers = { onundo: vi.fn(), onnext: vi.fn() };

  it("shows a spool with no swatch, and only the ring once recorded", () => {
    const { container } = render(ScanCard, { card: { ...spool, spoolId: null }, done: true });
    expect(container.querySelector(".ring")).toBeInTheDocument();
    expect(screen.queryByRole("heading")).toBeNull();
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("shows Info with the AMS remaining and a link to the spool, without a countdown", () => {
    render(ScanResult, { view: view({ outcome: "info" }), ...handlers });
    expect(screen.getByText("40% left, as the AMS last reported")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View spool" })).toHaveAttribute("href", "/spools/7");
    expect(screen.queryByRole("button", { name: "Undo" })).toBeNull();
    expect(screen.queryByText(/Ready for the next spool/)).toBeNull();
  });

  it("says when a recorded action was flagged", () => {
    render(ScanResult, {
      view: view({
        outcome: "recorded",
        message: "Recorded Opened, flagged for review.",
        tone: "warn",
        last: last(),
        countdown: { id: 1, ms: 3000 },
      }),
      ...handlers,
    });
    expect(screen.getByRole("heading", { name: "Opened" })).toBeInTheDocument();
    expect(screen.getByText("Recorded Opened, flagged for review.")).toHaveClass("warn");
    expect(screen.getByRole("button", { name: "Undo" })).toBeInTheDocument();
  });

  it("shows the message alone once the recorded action is undone", () => {
    render(ScanResult, {
      view: view({ outcome: "recorded", message: "Undid Opened.", last: last({ undone: true }) }),
      ...handlers,
    });
    expect(screen.queryByRole("heading", { name: "Opened" })).toBeNull();
    expect(screen.getByText("Undid Opened.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Undo" })).toBeNull();
  });

  it("names a recorded spool with no number yet without one", () => {
    render(ScanResult, {
      view: view({
        outcome: "recorded",
        message: "Recorded Opened.",
        card: null,
        last: last({ card: { ...spool, spoolId: null } }),
      }),
      ...handlers,
    });
    expect(screen.getByText("Recorded just now")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "View spool" })).toBeNull();
  });

  const DeliveryPanel = (await import("#lib/components/phone/DeliveryPanel.svelte")).default;
  const DeliveryList = (await import("#lib/components/phone/DeliveryList.svelte")).default;
  const panel = { onchoose: vi.fn(), onundo: vi.fn(), onnext: vi.fn(), ontoggle: vi.fn() };

  it("shows Looking it up in the delivery panel, without the toggle", () => {
    render(DeliveryPanel, { view: view({ phase: "looking_up", card: null }), ...panel });
    expect(screen.getByRole("status")).toHaveTextContent("Looking it up…");
    expect(screen.queryByRole("button", { name: "Delivery" })).toBeNull();
  });

  it("shows an offline card and a message while sending, with no countdown", () => {
    const { container } = render(DeliveryPanel, {
      view: view({
        phase: "sending",
        card: { ...spool, offline: true, spoolId: null },
        actions: ["received", "opened", "empty"],
        message: "Can't reach the server. Your choice will be queued.",
        tone: "warn",
      }),
      ...panel,
    });
    expect(screen.getByText("Offline")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New" })).toBeDisabled();
    expect(container.querySelector(".fill")).toBeNull();
  });

  it("says when a delivery spool was flagged, and shows messages alone", () => {
    const flagged = render(DeliveryPanel, {
      view: view({
        outcome: "recorded",
        message: "Recorded Opened, flagged for review.",
        tone: "warn",
        card: { ...spool, spoolId: null },
        last: last(),
      }),
      ...panel,
    });
    expect(screen.getByText("Recorded Opened")).toBeInTheDocument();
    expect(screen.getByText("Recorded Opened, flagged for review.")).toHaveClass("warn");
    expect(screen.getByText("PLA Basic #000000")).toBeInTheDocument();
    flagged.unmount();

    const notice = render(DeliveryPanel, { view: view({ message: null, card: null }), ...panel });
    expect(screen.queryByRole("button", { name: "Undo" })).toBeNull();
    notice.unmount();
    render(DeliveryPanel, { view: view({ message: null }), ...panel });
    expect(screen.getByText("PLA Basic #000000")).toHaveClass("message");
  });

  it("lists spools with no swatch or number", () => {
    render(DeliveryList, {
      rows: [
        {
          eventId: "e1",
          card: { ...spool, spoolId: null },
          action: "opened",
          at: 0,
          queued: false,
          undone: false,
        },
      ],
      totals: { received: 0, opened: 1, empty: 0 },
      undoable: "other",
      fresh: null,
      onundo: vi.fn(),
      onclear: vi.fn(),
    });
    expect(screen.getByRole("listitem")).not.toHaveTextContent(" · #");
    expect(screen.queryByRole("button", { name: "Undo" })).toBeNull(); // not the last scan
  });

  it("says Online, Offline, Away and the queue size in the header", () => {
    const theme = new Theme(document.createElement("html"), undefined, undefined);
    const header = render(ScanHeader, { reach: null, queueSize: 0, theme });
    expect(screen.queryByRole("status")).toBeNull();
    header.rerender({ reach: null, queueSize: 2, theme });
    expect(screen.getByRole("status")).toHaveTextContent("2 queued");
    header.rerender({ reach: "online", queueSize: 0, theme });
    expect(screen.getByRole("status")).toHaveTextContent("Online");
    expect(screen.getByRole("status")).not.toHaveClass("off");
    expect(screen.getByRole("status")).not.toHaveAttribute("title");
    header.rerender({ reach: "offline", queueSize: 3, theme });
    expect(screen.getByRole("status")).toHaveTextContent("Offline · 3 queued");
    expect(screen.getByRole("status")).toHaveClass("off");
    header.rerender({ reach: "away", queueSize: 1, theme });
    expect(screen.getByRole("status")).toHaveTextContent("Away · 1 queued");
    expect(screen.getByRole("status")).toHaveClass("off");
    expect(screen.getByRole("status")).toHaveAttribute(
      "title",
      "Away from home: scans are sent when you're back.",
    );
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
    expect(screen.queryByText("Suggested")).toBeNull();
  });
});
