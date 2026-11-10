/** Timing for the phone app's start screen (docs/SPEC.md, Phone scanner).
 *
 * The logo animation plays through at least one full cycle, so its ending (the check
 * landing) is always seen, and the screen stays until the app is ready, or LIMIT_MS at
 * most. The cycle's length is read from the animation itself, so a redesigned animation
 * needs no change here. */

/** The longest the start screen waits for the app to be ready (one heartbeat's answer). */
export const LIMIT_MS = 4000;

/** How long one full cycle of the animations under `root` lasts, in milliseconds: the
 * longest delay plus duration. 0 when nothing is animated (the phone's reduce-motion
 * setting turns the animation off) or the browser cannot tell. */
export function cycleMs(root: Element | null): number {
  if (!root || typeof root.getAnimations !== "function") return 0;
  let longest = 0;
  for (const animation of root.getAnimations({ subtree: true })) {
    const timing = animation.effect?.getComputedTiming();
    const delay = typeof timing?.delay === "number" ? timing.delay : 0;
    const duration = typeof timing?.duration === "number" ? timing.duration : 0;
    const end = delay + duration;
    if (Number.isFinite(end)) longest = Math.max(longest, end);
  }
  return longest;
}

/** How much longer the start screen stays, in milliseconds, `elapsed` ms after it opened:
 * until the cycle ends, and then until the app is ready or the limit passes. */
export function remainingMs(elapsed: number, cycle: number, ready: boolean): number {
  const until = ready ? cycle : Math.max(cycle, LIMIT_MS);
  return Math.max(until - elapsed, 0);
}
