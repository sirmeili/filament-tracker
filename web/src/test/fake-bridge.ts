/** A fake Android bridge for tests: in-memory secure storage, scripted tag reads and QR codes. */

import type { NfcStatus, PhoneBridge, TagRead } from "#lib/phone/bridge.ts";

export interface FakeBridge extends PhoneBridge {
  storage: Map<string, string>;
  status: NfcStatus;
  qr: (string | null | Error)[];
  /** Deliver a tag to the pending readTag call. */
  tap(read: TagRead): void;
  /** Make the pending readTag call fail, as when a tag is pulled away. */
  fail(): void;
  reads: number;
}

export function fakeBridge(status: NfcStatus = "ready"): FakeBridge {
  let pending: { resolve: (read: TagRead) => void; reject: (error: Error) => void } | null = null;
  const fake: FakeBridge = {
    app: true,
    appVersion: "app-test",
    storage: new Map(),
    status,
    qr: [],
    reads: 0,
    nfcStatus: () => Promise.resolve(fake.status),
    readTag: (_salt, signal) =>
      new Promise<TagRead>((resolve, reject) => {
        fake.reads += 1;
        pending = { resolve, reject };
        signal.addEventListener("abort", () => reject(new Error("aborted")));
      }),
    scanQr: () => {
      const next = fake.qr.shift() ?? null;
      return next instanceof Error ? Promise.reject(next) : Promise.resolve(next);
    },
    secureGet: (key) => Promise.resolve(fake.storage.get(key) ?? null),
    secureSet: (key, value) => {
      fake.storage.set(key, value);
      return Promise.resolve();
    },
    secureRemove: (key) => {
      fake.storage.delete(key);
      return Promise.resolve();
    },
    tap: (read) => {
      const current = pending;
      pending = null;
      current?.resolve(read);
    },
    fail: () => {
      const current = pending;
      pending = null;
      current?.reject(new Error("tag lost"));
    },
  };
  return fake;
}

export const PAIRING = {
  url: "https://filament.example.com",
  token: "ftd_abcdefghijklmnopqrstuvwxyz0123456789",
  deviceId: "phone-1",
};

export function tagRead(blocks: string[] = Array(48).fill("00".repeat(16))): TagRead {
  return { tagUid: "01020304", blocks, readOk: true };
}

/** A fetch that answers from a route table, recording what was asked. */
export function fakeFetch(
  routes: Record<string, (body: unknown) => { status: number; body?: unknown } | Error>,
): typeof fetch & { calls: { url: string; init: RequestInit }[] } {
  const calls: { url: string; init: RequestInit }[] = [];
  const fn = (async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = String(input);
    calls.push({ url, init });
    const key = `${init.method ?? "GET"} ${new URL(url).pathname}`;
    const handler = Object.entries(routes).find(([pattern]) => key.startsWith(pattern))?.[1];
    const answer = handler
      ? handler(init.body ? JSON.parse(String(init.body)) : undefined)
      : { status: 404 };
    if (answer instanceof Error) throw answer;
    return new Response(answer.body === undefined ? null : JSON.stringify(answer.body), {
      status: answer.status,
    });
  }) as typeof fetch & { calls: { url: string; init: RequestInit }[] };
  fn.calls = calls;
  return fn;
}
