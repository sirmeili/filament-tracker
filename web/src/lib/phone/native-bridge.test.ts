import { afterEach, describe, expect, it, vi } from "vitest";
import { bridge, browserBridge, setBridge } from "#lib/phone/bridge.ts";
import {
  installNativeBridge,
  nativeBridge,
  type FilamentTrackerPlugin,
} from "#lib/phone/native-bridge.ts";

const READ = { tagUid: "01020304", blocks: ["00".repeat(16)], readOk: true };

function fakePlugin() {
  let finishRead: { resolve: (r: typeof READ) => void; reject: (e: unknown) => void } | null = null;
  const storage = new Map<string, string>();
  const plugin = {
    appInfo: vi.fn(async () => ({ version: "1.0" })),
    nfcStatus: vi.fn(async () => ({ status: "no_mifare" as const })),
    readTag: vi.fn(
      () =>
        new Promise<typeof READ>((resolve, reject) => {
          finishRead = { resolve, reject };
        }),
    ),
    cancelRead: vi.fn(async () => {}),
    scanQr: vi.fn(async () => ({ value: "code" as string | null })),
    secureGet: vi.fn(async ({ key }: { key: string }) => ({ value: storage.get(key) ?? null })),
    secureSet: vi.fn(async ({ key, value }: { key: string; value: string }) => {
      storage.set(key, value);
    }),
    secureRemove: vi.fn(async ({ key }: { key: string }) => {
      storage.delete(key);
    }),
  } satisfies FilamentTrackerPlugin;
  return {
    plugin,
    storage,
    finish: (read: typeof READ) => finishRead?.resolve(read),
    fail: (error: unknown) => finishRead?.reject(error),
  };
}

afterEach(() => setBridge(browserBridge));

describe("native bridge", () => {
  it("passes the salt in and returns only the read", async () => {
    const fake = fakePlugin();
    const native = nativeBridge(fake.plugin, "1.0");

    const read = native.readTag("AABB", new AbortController().signal);
    fake.finish({ ...READ, extra: "ignored" } as typeof READ);

    expect(await read).toEqual(READ);
    expect(fake.plugin.readTag).toHaveBeenCalledWith({ salt: "AABB" });
  });

  it("cancels the native read when the page stops listening", async () => {
    const fake = fakePlugin();
    const native = nativeBridge(fake.plugin, "1.0");
    const stop = new AbortController();

    const read = native.readTag("AABB", stop.signal);
    stop.abort();

    await expect(read).rejects.toMatchObject({ name: "AbortError" });
    expect(fake.plugin.cancelRead).toHaveBeenCalledOnce();
    fake.finish(READ); // too late: ignored
  });

  it("does not start a read that was already cancelled", async () => {
    const fake = fakePlugin();
    const stop = new AbortController();
    stop.abort();

    await expect(nativeBridge(fake.plugin, "1.0").readTag("AA", stop.signal)).rejects.toThrow(
      /cancelled/,
    );
    expect(fake.plugin.readTag).not.toHaveBeenCalled();
  });

  it("passes a failed read on as an error", async () => {
    const fake = fakePlugin();
    const native = nativeBridge(fake.plugin, "1.0");

    const lost = native.readTag("AA", new AbortController().signal);
    fake.fail(new Error("tag read failed"));
    await expect(lost).rejects.toThrow("tag read failed");

    const odd = native.readTag("AA", new AbortController().signal);
    fake.fail("not an error");
    await expect(odd).rejects.toThrow("tag read failed");
  });

  it("ignores a failed cancel", async () => {
    const fake = fakePlugin();
    fake.plugin.cancelRead.mockRejectedValue(new Error("gone"));
    const stop = new AbortController();
    const read = nativeBridge(fake.plugin, "1.0").readTag("AA", stop.signal);
    stop.abort();
    await expect(read).rejects.toMatchObject({ name: "AbortError" });
  });

  it("reports NFC status, QR codes and storage from the plugin", async () => {
    const fake = fakePlugin();
    const native = nativeBridge(fake.plugin, "1.0");

    expect(native.app).toBe(true);
    expect(native.appVersion).toBe("app-1.0");
    expect(await native.nfcStatus()).toBe("no_mifare");
    expect(await native.scanQr()).toBe("code");
    fake.plugin.scanQr.mockResolvedValue({ value: null });
    expect(await native.scanQr()).toBeNull();
    fake.plugin.scanQr.mockResolvedValue({} as { value: null });
    expect(await native.scanQr()).toBeNull();

    expect(await native.secureGet("pairing")).toBeNull();
    await native.secureSet("pairing", "x");
    expect(await native.secureGet("pairing")).toBe("x");
    await native.secureRemove("pairing");
    expect(fake.storage.size).toBe(0);
    fake.plugin.secureGet.mockResolvedValue({} as { value: null });
    expect(await native.secureGet("pairing")).toBeNull();
  });
});

describe("installing the bridge", () => {
  it("does nothing in a browser", async () => {
    const plugin = vi.fn();
    expect(await installNativeBridge({ isNativePlatform: () => false }, plugin)).toBe(false);
    expect(plugin).not.toHaveBeenCalled();
    expect(bridge()).toBe(browserBridge);
  });

  it("connects to the plugin in the app, with the app's version", async () => {
    const fake = fakePlugin();
    expect(await installNativeBridge({ isNativePlatform: () => true }, () => fake.plugin)).toBe(
      true,
    );
    expect(bridge().app).toBe(true);
    expect(bridge().appVersion).toBe("app-1.0");
  });

  it("uses Capacitor by default, which is not native under test", async () => {
    expect(await installNativeBridge()).toBe(false);
  });
});
