/** The phone app away from home: Cloudflare Access in front of the server, the server
 * refusing scans from outside the LAN, and queued scans that must never be lost. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { accessHeaders, api, ApiError, setAccessToken, setApiBase } from "#lib/api/client.ts";
import { browserBridge, setBridge } from "#lib/phone/bridge.ts";
import {
  AwayError,
  DeviceApi,
  isAway,
  keepQueued,
  reachOf,
  scanEvent,
  type ScanEvent,
  type ScanResult,
} from "#lib/phone/device-api.ts";
import { loadAccess, loadSalt, saveAccess, savePairing } from "#lib/phone/pairing-store.ts";
import { phone } from "#lib/phone/phone-state.svelte.ts";
import { OfflineQueue, type QueueStore } from "#lib/phone/queue.ts";
import { ScanFlow } from "#lib/phone/scan-flow.ts";
import { PhoneSession } from "#lib/phone/session.ts";
import {
  fakeBridge,
  fakeFetch,
  PAIRING,
  tagRead,
  type FakeAnswer,
  type FakeBridge,
} from "../../test/fake-bridge.ts";
import tags from "../../test/tags.json";

// A made-up Access service token, in Cloudflare's format.
const ACCESS = {
  clientId: "0123456789abcdef0123456789abcdef.access",
  clientSecret: "made-up-client-secret-0123456789abcdef",
};
const NEW_ACCESS = {
  clientId: "fedcba9876543210fedcba9876543210.access",
  clientSecret: "x".repeat(40),
};
const AWAY: FakeAnswer = {
  status: 403,
  body: { detail: "tokens are accepted only from the local network" },
  headers: { "X-Rollcall-Refused": "local-network-only" },
};
// What Cloudflare Access sends after its redirect when the app has no valid token.
const SIGN_IN_PAGE: FakeAnswer = {
  status: 200,
  text: "<!doctype html><title>Sign in ・ Cloudflare Access</title>",
};
const OK_SCAN: FakeAnswer = { status: 200, body: {} };

let native: FakeBridge;

beforeEach(() => {
  native = fakeBridge();
  setBridge(native);
});

afterEach(async () => {
  setBridge(native);
  await phone.unpair();
  setBridge(browserBridge);
  setApiBase("");
  setAccessToken(null);
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function headersOf(call: { init: RequestInit }): Headers {
  return new Headers(call.init.headers);
}

describe("the server's away refusal", () => {
  it("turns the local-network-only refusal into Away", async () => {
    const fetch = fakeFetch({ "POST /api/v1/scans": () => AWAY });
    const error = await new DeviceApi(PAIRING, fetch)
      .scan(scanEvent(PAIRING, tagRead(), "lookup", "1"))
      .catch((e: unknown) => e);

    expect(error).toBeInstanceOf(AwayError);
    expect(error).toMatchObject({
      status: 403,
      message: "tokens are accepted only from the local network",
    });
    expect(isAway(error)).toBe(true);
    expect(keepQueued(error)).toBe(true);
    expect(reachOf(error)).toBe("away");
  });

  it("keeps other refusals as refusals", async () => {
    const fetch = fakeFetch({
      "POST /api/v1/scans": () => ({ status: 403, body: { detail: "no" } }),
    });
    const error = await new DeviceApi(PAIRING, fetch)
      .scan(scanEvent(PAIRING, tagRead(), "lookup", "1"))
      .catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(isAway(error)).toBe(false);
    expect(keepQueued(error)).toBe(false);
    expect(reachOf(error)).toBe("online");
    expect(reachOf(new ApiError(0, "down"))).toBe("offline");
    expect(keepQueued(new Error("boom"))).toBe(true);
  });

  it("uses a default message when the refusal has no detail", async () => {
    const fetch = fakeFetch({ "POST /api/v1/scans": () => ({ ...AWAY, body: undefined }) });
    await expect(
      new DeviceApi(PAIRING, fetch).scan(scanEvent(PAIRING, tagRead(), "lookup", "1")),
    ).rejects.toMatchObject({ message: "Away from the home network" });
  });
});

describe("the Access token", () => {
  it("reads it from provisioning", async () => {
    const fetch = fakeFetch({
      "GET /api/v1/devices/provisioning": () => ({
        status: 200,
        body: {
          kdf_salt: "AA",
          access: { client_id: ACCESS.clientId, client_secret: ACCESS.clientSecret },
        },
      }),
    });

    expect(await new DeviceApi(PAIRING, fetch).provisioning()).toEqual({
      salt: "AA",
      access: ACCESS,
      records: true,
    });
  });

  it("goes with scanner and page requests to an HTTPS server, once set", async () => {
    const fetch = fakeFetch({ "POST /api/v1/devices/heartbeat": () => ({ status: 204 }) });
    const device = new DeviceApi(PAIRING, fetch);
    await device.heartbeat("1", 0);
    expect(headersOf(fetch.calls[0]).has("CF-Access-Client-Id")).toBe(false);

    setAccessToken(ACCESS);
    await device.heartbeat("1", 0);
    setApiBase(PAIRING.url);
    const page = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true })));
    await api("/inventory", {}, page);

    const sent = headersOf(fetch.calls[1]);
    expect(sent.get("CF-Access-Client-Id")).toBe(ACCESS.clientId);
    expect(sent.get("CF-Access-Client-Secret")).toBe(ACCESS.clientSecret);
    const pageHeaders = new Headers((page.mock.calls[0][1] as RequestInit).headers);
    expect(pageHeaders.get("CF-Access-Client-Secret")).toBe(ACCESS.clientSecret);
  });

  it("is never sent over plain HTTP", async () => {
    setAccessToken(ACCESS);
    const fetch = fakeFetch({ "POST /api/v1/devices/heartbeat": () => ({ status: 204 }) });

    await new DeviceApi({ ...PAIRING, url: "http://192.168.1.20:8000" }, fetch).heartbeat("1", 0);

    expect(headersOf(fetch.calls[0]).has("CF-Access-Client-Secret")).toBe(false);
    expect(accessHeaders("http://192.168.1.20:8000/api/v1/x")).toEqual({});
    expect(accessHeaders("HTTPS://rollcall.example.com/api/v1/x")).toHaveProperty(
      "CF-Access-Client-Id",
    );
  });
});

describe("queued scans away from home", () => {
  async function sessionWith(
    answer: () => FakeAnswer,
    home: () => FakeAnswer = answer,
    scans: () => FakeAnswer = answer,
  ) {
    await savePairing(PAIRING, "AA");
    const fetch = fakeFetch({
      "POST /api/v1/devices/heartbeat": home,
      "POST /api/v1/scans": scans,
      "GET /api/v1/devices/provisioning": answer,
    });
    const session = (await PhoneSession.open(native, fetch))!;
    await session.queue.add(scanEvent(PAIRING, tagRead(), "opened", "1"), Date.now());
    return { session, fetch };
  }

  it("are kept when Cloudflare Access answers with its sign-in page", async () => {
    const { session, fetch } = await sessionWith(() => SIGN_IN_PAGE);

    await session.beat();
    await session.retry(true);

    expect(session.reach).toBe("offline");
    expect(session.queue.size).toBe(1);
    expect(fetch.calls.some((call) => call.url.endsWith("/provisioning"))).toBe(false);
  });

  it("are kept while the server says the phone is away, and sent once it is home", async () => {
    let home = false;
    const { session, fetch } = await sessionWith(
      () => AWAY,
      () => (home ? { status: 204 } : AWAY),
      () => (home ? OK_SCAN : AWAY),
    );

    await session.beat();
    await session.retry(true);
    expect(session.reach).toBe("away");
    expect(session.queue.size).toBe(1);
    expect(fetch.calls.some((call) => call.url.endsWith("/provisioning"))).toBe(false);

    home = true;
    await session.beat();
    await vi.waitFor(() => expect(session.queue.size).toBe(0));
    expect(session.reach).toBe("online");
  });
});

describe("scanning away from home", () => {
  function memory(): QueueStore {
    let text: string | null = null;
    return {
      load: async () => text,
      save: async (value) => {
        text = value;
      },
    };
  }

  async function flowWith(scan: (event: ScanEvent) => Promise<ScanResult>) {
    const reached: string[] = [];
    const api = { scan: vi.fn(scan), revert: vi.fn().mockRejectedValue(new AwayError("away")) };
    const queue = await OfflineQueue.open(memory());
    const flow = new ScanFlow({
      api,
      queue,
      pairing: PAIRING,
      appVersion: "app-1",
      onReach: (reach) => reached.push(reach),
    });
    return { flow, queue, reached };
  }

  const blackTag = () => tagRead(tags[0].blocks);

  it("decodes the tag on the phone and queues the choice for home", async () => {
    vi.useFakeTimers();
    const { flow, queue, reached } = await flowWith(() => Promise.reject(new AwayError("away")));

    await flow.tapped(blackTag());
    expect(flow.view).toMatchObject({
      phase: "choosing",
      actions: ["received", "opened", "empty"],
      message: "You're away from home. Your choice will be queued.",
      card: { offline: true },
    });
    await flow.choose("opened");

    expect(queue.size).toBe(1);
    expect(flow.view.message).toBe("Queued Opened. It will be sent when you're home.");
    expect(reached).toEqual(["away"]);
  });

  it("queues a choice the server refuses as away after the lookup", async () => {
    vi.useFakeTimers();
    const { flow, queue } = await flowWith(async (event) => {
      if (event.action === "lookup") {
        return {
          feedback: "ok",
          event_id: null,
          state: "sealed",
          product: null,
          spool: null,
          actions: ["opened", "empty", "cancel"],
          suggested: "opened",
          placeholder: false,
        };
      }
      throw new AwayError("away");
    });

    await flow.tapped(blackTag());
    await flow.choose("opened");

    expect(queue.size).toBe(1);
    expect(flow.view.message).toMatch(/sent when you're home/);
  });

  it("says undo works at home", async () => {
    vi.useFakeTimers();
    let away = false;
    const { flow } = await flowWith(async () => {
      if (away) throw new AwayError("away");
      return {
        feedback: "ok",
        event_id: "e1",
        state: "open",
        product: null,
        spool: null,
        actions: ["opened"],
        suggested: "opened",
        placeholder: false,
      };
    });
    await flow.tapped(blackTag());
    await flow.choose("opened");
    away = true;

    await flow.undoLast();

    expect(flow.view.message).toBe("You're away from home. This works on your home network.");
  });
});

describe("keeping the Access token current", () => {
  function provisioning(salt: string, access: typeof ACCESS | null): FakeAnswer {
    return {
      status: 200,
      body: {
        kdf_salt: salt,
        access: access && { client_id: access.clientId, client_secret: access.clientSecret },
      },
    };
  }

  it("pairing keeps the token, and unlinking forgets it", async () => {
    vi.stubGlobal(
      "fetch",
      fakeFetch({
        "GET /api/v1/devices/provisioning": () => provisioning("AA", ACCESS),
        "POST /api/v1/devices/heartbeat": () => ({ status: 204 }),
      }),
    );

    await phone.pair(PAIRING);

    expect(await loadAccess()).toEqual(ACCESS);
    expect(accessHeaders(PAIRING.url)).toHaveProperty("CF-Access-Client-Id", ACCESS.clientId);
    await phone.unpair();
    expect(await loadAccess()).toBeNull();
    expect(accessHeaders(PAIRING.url)).toEqual({});
  });

  it("fetches it again at home when the app starts and comes back to the front", async () => {
    vi.useFakeTimers();
    await savePairing(PAIRING, "AA");
    await saveAccess(ACCESS);
    let served = provisioning("BB", NEW_ACCESS);
    const fetch = fakeFetch({
      "POST /api/v1/devices/heartbeat": () => ({ status: 204 }),
      "GET /api/v1/devices/provisioning": () => served,
    });
    const session = (await PhoneSession.open(native, fetch))!;
    expect(session.access).toEqual(ACCESS);

    session.start();
    await vi.advanceTimersByTimeAsync(0);

    expect(await loadAccess()).toEqual(NEW_ACCESS);
    expect(await loadSalt()).toBe("BB");
    expect(session.salt).toBe("BB");
    expect(accessHeaders(PAIRING.url)).toHaveProperty("CF-Access-Client-Id", NEW_ACCESS.clientId);

    // The server's token is taken away: the phone drops it the next time it is home.
    served = provisioning("BB", null);
    await session.beat(); // not refreshed on every heartbeat
    expect(await loadAccess()).toEqual(NEW_ACCESS);
    document.dispatchEvent(new Event("visibilitychange"));
    await vi.advanceTimersByTimeAsync(0);

    expect(await loadAccess()).toBeNull();
    expect(accessHeaders(PAIRING.url)).toEqual({});
    session.stop();
  });

  it("keeps the stored token when fetching it fails, and tries again", async () => {
    await savePairing(PAIRING, "AA");
    await saveAccess(ACCESS);
    let up = false;
    const fetch = fakeFetch({
      "POST /api/v1/devices/heartbeat": () => ({ status: 204 }),
      "GET /api/v1/devices/provisioning": () =>
        up ? provisioning("AA", NEW_ACCESS) : { status: 503, body: { detail: "no salt" } },
    });
    const session = (await PhoneSession.open(native, fetch))!;

    await session.beat();
    expect(await loadAccess()).toEqual(ACCESS);

    up = true;
    await session.beat();
    expect(await loadAccess()).toEqual(NEW_ACCESS);
  });

  it("reads a damaged stored token as none", async () => {
    native.storage.set("cf_access", "{not json");
    expect(await loadAccess()).toBeNull();
    native.storage.set("cf_access", JSON.stringify({ clientId: 1 }));
    expect(await loadAccess()).toBeNull();
  });
});
