import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, setApiBase } from "#lib/api/client.ts";
import { phoneName, requestOwnPhone, setUpError } from "#lib/phone/own-phone.ts";
import { fakeFetch, PAIRING } from "../../test/fake-bridge.ts";

const PIXEL =
  "Mozilla/5.0 (Linux; Android 15; Pixel 9 Pro XL Build/AP4A.250105.002; wv) AppleWebKit/537.36";

afterEach(() => setApiBase(""));

describe("the phone's name", () => {
  it("is the model from the app's user agent", () => {
    expect(phoneName(PIXEL)).toBe("Pixel 9 Pro XL");
    expect(phoneName("Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit")).toBe("SM-S918B");
  });

  it("falls back when the model is hidden or missing", () => {
    expect(phoneName("Mozilla/5.0 (Linux; Android 10; K) AppleWebKit")).toBe("Android phone");
    expect(phoneName("Mozilla/5.0 (X11; Linux x86_64)")).toBe("Android phone");
    expect(phoneName("Mozilla/5.0 (Linux; Android 15; wv)")).toBe("Android phone");
  });

  it("drops control characters and keeps it short", () => {
    expect(phoneName(`(Linux; Android 15; Pix${String.fromCharCode(127)}el\u0007 9)`)).toBe(
      "Pixel 9",
    );
    expect(phoneName(`(Linux; Android 15; ${"P".repeat(80)})`)).toHaveLength(60);
  });

  it("reads the browser's user agent by default", () => {
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue(PIXEL);
    expect(phoneName()).toBe("Pixel 9 Pro XL");
    vi.restoreAllMocks();
  });
});

describe("asking for the phone's own token", () => {
  it("posts the phone's name as the signed-in user and returns the pairing", async () => {
    setApiBase(PAIRING.url);
    const fetch = fakeFetch({
      "POST /api/v1/devices/mine": () => ({
        status: 201,
        body: { id: "phone-1", token: PAIRING.token, owner: "bob" },
      }),
    });

    const fields = await requestOwnPhone(PAIRING.url, "Pixel 9", fetch);

    expect(fields).toEqual({ url: PAIRING.url, token: PAIRING.token, deviceId: "phone-1" });
    expect(JSON.parse(String(fetch.calls[0].init.body))).toEqual({ name: "Pixel 9" });
    expect(fetch.calls[0].init.credentials).toBe("include");
  });
});

describe("why setting up failed", () => {
  it("says to finish at home when refused away from home", () => {
    expect(setUpError(new ApiError(403, "x"))).toEqual({
      away: true,
      text: expect.stringContaining("Finish setting up at home"),
    });
  });

  it("explains the other failures", () => {
    expect(setUpError(new ApiError(409, "unlink one first")).text).toBe("unlink one first");
    expect(setUpError(new ApiError(0, "down")).text).toMatch(/Can't reach the server/);
    expect(setUpError(new ApiError(503, "no salt")).text).toMatch(/BAMBU_KDF_SALT/);
    expect(setUpError(new ApiError(500, "boom")).text).toMatch(/failed/);
    expect(setUpError(new Error("x"))).toEqual({ away: false, text: expect.any(String) });
  });
});
