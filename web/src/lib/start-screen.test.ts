import { cleanup, render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import StartScreen from "#lib/components/phone/StartScreen.svelte";
import { cycleMs, LIMIT_MS, remainingMs } from "#lib/start-screen.ts";

/** An element whose animations have these delays and durations (jsdom has none). */
function animated(...timings: { delay?: number; duration: number | string }[]): Element {
  const element = document.createElement("div");
  element.getAnimations = () =>
    timings.map(
      (timing) =>
        ({
          effect: { getComputedTiming: () => ({ delay: 0, ...timing }) },
        }) as unknown as Animation,
    );
  return element;
}

describe("the start screen's timing", () => {
  it("reads one cycle from the longest animation", () => {
    expect(cycleMs(animated({ duration: 2400 }, { delay: 300, duration: 2400 }))).toBe(2700);
    expect(cycleMs(animated({ duration: "auto" }, { duration: 1000 }))).toBe(1000);
    expect(cycleMs(animated({ duration: Infinity }, { duration: 500 }))).toBe(500);
  });

  it("is 0 with nothing animated or no way to tell", () => {
    expect(cycleMs(null)).toBe(0);
    expect(cycleMs(document.createElement("div"))).toBe(0); // jsdom: no getAnimations
    expect(cycleMs(animated())).toBe(0); // reduce motion: the animation is off
    const blank = document.createElement("div");
    blank.getAnimations = () => [{ effect: null } as unknown as Animation];
    expect(cycleMs(blank)).toBe(0);
  });

  it("waits for the cycle, then for the app or the limit", () => {
    expect(remainingMs(1000, 2400, true)).toBe(1400);
    expect(remainingMs(3000, 2400, true)).toBe(0);
    expect(remainingMs(1000, 2400, false)).toBe(LIMIT_MS - 1000);
    expect(remainingMs(1000, 6000, false)).toBe(5000); // a cycle longer than the limit
    expect(remainingMs(LIMIT_MS + 1, 0, false)).toBe(0);
  });
});

describe("the start screen", () => {
  const original = HTMLElement.prototype.getAnimations;

  beforeEach(() => vi.useFakeTimers());

  afterEach(() => {
    cleanup();
    HTMLElement.prototype.getAnimations = original;
    vi.useRealTimers();
  });

  function cycleOf(ms: number): void {
    HTMLElement.prototype.getAnimations = function () {
      return [
        { effect: { getComputedTiming: () => ({ delay: 0, duration: ms }) } },
      ] as unknown as Animation[];
    };
  }

  it("shows the logo animation and plays one full cycle even when the app is ready", async () => {
    cycleOf(2400);
    const ondone = vi.fn();
    render(StartScreen, { ready: true, ondone });

    expect(screen.getByRole("img", { name: /^Roll Call/ })).toBeInTheDocument();
    await vi.advanceTimersByTimeAsync(2399);
    expect(ondone).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(ondone).toHaveBeenCalledTimes(1);
  });

  it("stays until the app is ready, then ends at once", async () => {
    cycleOf(1000);
    const ondone = vi.fn();
    const view = render(StartScreen, { ready: false, ondone });

    await vi.advanceTimersByTimeAsync(2000);
    expect(ondone).not.toHaveBeenCalled();
    await view.rerender({ ready: true, ondone });
    await vi.advanceTimersByTimeAsync(0);
    expect(ondone).toHaveBeenCalledTimes(1);
  });

  it("gives up waiting at the limit", async () => {
    cycleOf(1000);
    const ondone = vi.fn();
    render(StartScreen, { ready: false, ondone });

    await vi.advanceTimersByTimeAsync(LIMIT_MS);
    expect(ondone).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(LIMIT_MS);
    expect(ondone).toHaveBeenCalledTimes(1);
  });

  it("ends as soon as the app is ready when the animation is off", async () => {
    cycleOf(0);
    const ondone = vi.fn();
    render(StartScreen, { ready: true, ondone });

    await vi.advanceTimersByTimeAsync(0);
    expect(ondone).toHaveBeenCalledTimes(1);
  });
});
