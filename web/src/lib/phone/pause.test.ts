import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { pause } from "#lib/phone/pause.ts";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("pause", () => {
  it("waits for the time given", async () => {
    let done = false;
    const waiting = pause(1000, new AbortController().signal).then(() => (done = true));
    await vi.advanceTimersByTimeAsync(999);
    expect(done).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    await waiting;
    expect(done).toBe(true);
  });

  it("ends early when the signal aborts", async () => {
    const stop = new AbortController();
    const waiting = pause(60_000, stop.signal);
    stop.abort();
    await waiting;
    await pause(60_000, stop.signal); // already aborted
    expect(vi.getTimerCount()).toBe(0);
  });
});
