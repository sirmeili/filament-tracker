/** The phone's Scan screen logic, mirroring the scanner (docs/SPEC.md, User workflows).
 *
 * Tap a spool: look it up, show the card and the actions for its state, wait up to 15
 * seconds for a choice, send it, show the result for 3 seconds, then go back to waiting for
 * a tap. The same action confirmed for the same spool within 30 seconds is sent once. When
 * the server cannot be reached, the card comes from the phone's own decode, New, Opened and
 * Empty are offered, and the choice is queued.
 */

import { ApiError } from "#lib/api/client.ts";
import type { TagRead } from "#lib/phone/bridge.ts";
import {
  isAway,
  isOffline,
  reachOf,
  scanEvent,
  type Reach,
  type DeviceApi,
  type Feedback,
  type ScanAction,
  type ScanResult,
  type ScreenAction,
} from "#lib/phone/device-api.ts";
import type { Pairing } from "#lib/phone/pairing-store.ts";
import type { OfflineQueue } from "#lib/phone/queue.ts";
import { decodeOffline, offlineName } from "#lib/phone/tag-decode.ts";

export const CHOICE_TIMEOUT_MS = 15_000;
export const RESULT_MS = 3_000;
export const REPEAT_WINDOW_MS = 30_000;
const OFFLINE_ACTIONS: ScreenAction[] = ["received", "opened", "empty"];

export type Phase = "idle" | "looking_up" | "choosing" | "sending" | "result";
export type Tone = "ok" | "warn" | "error";

export interface Card {
  name: string;
  colorRgba: string | null;
  /** The spool's state, or null when unknown (a new tag, or offline). */
  state: string | null;
  receivedAt: string | null;
  openedAt: string | null;
  emptiedAt: string | null;
  remainingPct: number | null;
  spoolId: number | null;
  placeholder: boolean;
  offline: boolean;
}

export interface LastScan {
  card: Card;
  tagUid: string;
  action: ScanAction;
  eventId: string;
  at: number;
  queued: boolean;
  undone: boolean;
}

/** What a result screen shows: an action recorded or queued, Info, or a message. */
export type Outcome = "recorded" | "queued" | "info" | "notice";

/** A running timer, for the screen's countdown bar. A new id starts a new bar. */
export interface Countdown {
  id: number;
  ms: number;
}

export interface FlowView {
  phase: Phase;
  outcome: Outcome | null;
  countdown: Countdown | null;
  card: Card | null;
  actions: (ScreenAction | null)[];
  suggested: ScreenAction | null;
  message: string | null;
  tone: Tone;
  last: LastScan | null;
}

type Api = Pick<DeviceApi, "scan" | "revert">;

export interface FlowDeps {
  api: Api;
  queue: OfflineQueue;
  pairing: Pairing;
  appVersion: string;
  now?: () => number;
  newId?: () => string;
  /** Told whether the server answered, after each request (for the Online pill). */
  onReach?: (reach: Reach) => void;
}

const ACTION_NAMES: Record<ScanAction, string> = {
  received: "New",
  opened: "Opened",
  empty: "Empty",
  lookup: "Lookup",
};

/** "New", "Opened" or "Empty": a recorded action's name. */
export function actionName(action: ScanAction): string {
  return ACTION_NAMES[action];
}

export function actionLabel(action: ScreenAction): string {
  return action === "received" ? "New" : action[0].toUpperCase() + action.slice(1);
}

export function feedbackText(feedback: Feedback, action: ScanAction, state: string): string {
  const name = ACTION_NAMES[action];
  switch (feedback) {
    case "ok":
      return `Recorded ${name}.`;
    case "ok_created":
      return `Added as a new spool and recorded ${name}.`;
    case "already_in_state":
      return `Already ${state}. Nothing changed.`;
    case "flagged":
      return `Recorded ${name}, flagged for review.`;
    case "unreadable":
      return "Couldn't read this tag. Hold the phone still on it and try again.";
    default:
      return "The server couldn't record that.";
  }
}

/** Why the server refused the phone, in words; null for anything else. */
export function refusalText(error: unknown): string | null {
  if (isAway(error)) return "You're away from home. This works on your home network.";
  if (!(error instanceof ApiError)) return null;
  if (error.status === 401) return "This phone's token is no longer valid. Pair it again.";
  if (error.status === 403) return "The server accepts scans only from your home network.";
  return null;
}

function cardFrom(result: ScanResult): Card {
  return {
    name: result.product?.display_name ?? "Unknown spool",
    colorRgba: result.product?.color_rgba ?? null,
    state: result.spool ? result.state : null,
    receivedAt: result.spool?.received_at ?? null,
    openedAt: result.spool?.opened_at ?? null,
    emptiedAt: result.spool?.emptied_at ?? null,
    remainingPct: result.spool?.remaining_pct ?? null,
    spoolId: result.spool?.id ?? null,
    placeholder: result.placeholder,
    offline: false,
  };
}

const IDLE: FlowView = {
  phase: "idle",
  outcome: null,
  countdown: null,
  card: null,
  actions: [],
  suggested: null,
  message: null,
  tone: "ok",
  last: null,
};

export class ScanFlow {
  /** Whether the last answer said the phone is away from home. */
  private away = false;
  private current: FlowView = IDLE;
  private read: TagRead | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private timers = 0;
  private listeners = new Set<(view: FlowView) => void>();
  private readonly now: () => number;
  private readonly newId: () => string;

  constructor(private readonly deps: FlowDeps) {
    this.now = deps.now ?? Date.now;
    this.newId = deps.newId ?? (() => crypto.randomUUID());
  }

  get view(): FlowView {
    return this.current;
  }

  subscribe(listener: (view: FlowView) => void): () => void {
    this.listeners.add(listener);
    listener(this.current);
    return () => this.listeners.delete(listener);
  }

  /** Resolves once the screen is back to waiting for a tap, or when the signal aborts. */
  whenIdle(signal: AbortSignal): Promise<void> {
    if (this.current.phase === "idle" || signal.aborted) return Promise.resolve();
    return new Promise((resolve) => {
      const done = () => {
        this.listeners.delete(listener);
        signal.removeEventListener("abort", done);
        resolve();
      };
      const listener = (view: FlowView) => {
        if (view.phase === "idle") done();
      };
      this.listeners.add(listener);
      signal.addEventListener("abort", done, { once: true });
    });
  }

  /** A tag was tapped: look it up and offer its actions. */
  async tapped(read: TagRead): Promise<void> {
    if (this.current.phase === "sending" || this.current.phase === "looking_up") return;
    this.clearTimer();
    this.read = read;
    this.set({ phase: "looking_up", card: null, actions: [], suggested: null, message: null });
    let result: ScanResult;
    try {
      result = await this.reach(this.deps.api.scan(this.event(read, "lookup")));
    } catch (error) {
      this.lookupFailed(read, error);
      return;
    }
    if (result.feedback === "unreadable" || result.feedback === "error") {
      this.showResult(
        feedbackText(result.feedback, "lookup", result.state),
        "error",
        null,
        "notice",
      );
      return;
    }
    this.offer(cardFrom(result), result.actions, result.suggested);
  }

  /** The user chose an action from the card. */
  async choose(action: ScreenAction): Promise<void> {
    const read = this.read;
    const card = this.current.card;
    if (this.current.phase !== "choosing" || !read || !card) return;
    this.clearTimer();
    if (action === "cancel") {
      this.toIdle();
      return;
    }
    if (action === "info") {
      this.set({ phase: "result", outcome: "info", countdown: null, message: null, tone: "ok" });
      return;
    }
    const last = this.current.last;
    if (
      last &&
      !last.undone &&
      last.tagUid === read.tagUid &&
      last.action === action &&
      this.now() - last.at < REPEAT_WINDOW_MS
    ) {
      this.showResult(`${ACTION_NAMES[action]} was already recorded.`, "ok", card, "notice");
      return;
    }
    const event = this.event(read, action);
    const remember = (queued: boolean): LastScan => ({
      card,
      tagUid: read.tagUid,
      action,
      eventId: event.event_id,
      at: this.now(),
      queued,
      undone: false,
    });
    if (card.offline) {
      await this.enqueue(event, remember(true), card);
      return;
    }
    this.set({ phase: "sending", countdown: null });
    try {
      const result = await this.reach(this.deps.api.scan(event));
      const tone: Tone = result.feedback === "flagged" ? "warn" : "ok";
      // Remember the spool as the server now has it (a new tag gets its spool number).
      const after = result.product ? cardFrom(result) : card;
      this.set({ last: { ...remember(false), card: after } });
      this.showResult(
        feedbackText(result.feedback, action, result.state),
        tone,
        after,
        result.feedback === "already_in_state" ? "notice" : "recorded",
      );
    } catch (error) {
      if (isOffline(error) || isAway(error)) {
        await this.enqueue(event, remember(true), card);
      } else {
        const text = refusalText(error) ?? "The server couldn't record that.";
        this.showResult(text, "error", card, "notice");
      }
    }
  }

  /** Undo the last recorded scan: revert it, or take it out of the queue if not sent yet. */
  async undoLast(): Promise<void> {
    const last = this.current.last;
    if (!last || last.undone || this.current.phase === "sending") return;
    let message: string;
    if (last.queued && (await this.deps.queue.remove(last.eventId))) {
      message = `Removed the queued ${ACTION_NAMES[last.action]}.`;
    } else {
      try {
        await this.reach(this.deps.api.revert(last.eventId));
        message = `Undid ${ACTION_NAMES[last.action]}.`;
      } catch (error) {
        this.set({ message: refusalText(error) ?? "Couldn't undo it. Try again.", tone: "error" });
        return;
      }
    }
    this.set({ last: { ...last, undone: true }, message, tone: "ok" });
  }

  /** Close the card or result now. */
  dismiss(): void {
    this.clearTimer();
    this.toIdle();
  }

  stop(): void {
    this.clearTimer();
    this.listeners.clear();
  }

  private lookupFailed(read: TagRead, error: unknown): void {
    const refusal = isAway(error) ? null : refusalText(error);
    if (refusal || !(isOffline(error) || isAway(error))) {
      const text = refusal ?? "The server couldn't look up this spool.";
      this.showResult(text, "error", null, "notice");
      return;
    }
    const tag = decodeOffline(read.blocks);
    if (!tag) {
      this.showResult(
        "Can't reach the server, and this tag couldn't be read on the phone.",
        "error",
        null,
        "notice",
      );
      return;
    }
    const card: Card = {
      name: offlineName(tag),
      colorRgba: tag.colorRgba,
      state: null,
      receivedAt: null,
      openedAt: null,
      emptiedAt: null,
      remainingPct: null,
      spoolId: null,
      placeholder: false,
      offline: true,
    };
    const why = this.away ? "You're away from home." : "Can't reach the server.";
    this.offer(card, OFFLINE_ACTIONS, null, `${why} Your choice will be queued.`);
  }

  private offer(
    card: Card,
    actions: (ScreenAction | null)[],
    suggested: ScreenAction | null,
    message: string | null = null,
  ): void {
    this.set({
      phase: "choosing",
      outcome: null,
      countdown: this.countdown(CHOICE_TIMEOUT_MS),
      card,
      actions,
      suggested,
      message,
      tone: message ? "warn" : "ok",
    });
    this.timer = setTimeout(() => this.toIdle(), CHOICE_TIMEOUT_MS);
  }

  private async enqueue(
    event: ReturnType<ScanFlow["event"]>,
    last: LastScan,
    card: Card,
  ): Promise<void> {
    if (await this.deps.queue.add(event, this.now())) {
      this.set({ last });
      this.showResult(
        this.away
          ? `Queued ${ACTION_NAMES[last.action]}. It will be sent when you're home.`
          : `Queued ${ACTION_NAMES[last.action]}. It will be sent when the server is back.`,
        "warn",
        card,
        "queued",
      );
    } else {
      const text = "The queue is full. Connect to the server, then scan again.";
      this.showResult(text, "error", card, "notice");
    }
  }

  private showResult(message: string, tone: Tone, card: Card | null, outcome: Outcome): void {
    this.set({
      phase: "result",
      outcome,
      countdown: this.countdown(RESULT_MS),
      card,
      actions: [],
      suggested: null,
      message,
      tone,
    });
    this.timer = setTimeout(() => this.toIdle(), RESULT_MS);
  }

  private countdown(ms: number): Countdown {
    this.timers += 1;
    return { id: this.timers, ms };
  }

  /** Report whether the server answered, then pass the result or error on. */
  private async reach<T>(request: Promise<T>): Promise<T> {
    try {
      const result = await request;
      this.away = false;
      this.deps.onReach?.("online");
      return result;
    } catch (error) {
      const reach = reachOf(error);
      this.away = reach === "away";
      this.deps.onReach?.(reach);
      throw error;
    }
  }

  private toIdle(): void {
    this.timer = null;
    this.read = null;
    this.set({ ...IDLE, last: this.current.last, message: null });
  }

  private clearTimer(): void {
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
  }

  private event(read: TagRead, action: ScanAction) {
    return scanEvent(
      this.deps.pairing,
      read,
      action,
      this.deps.appVersion,
      new Date(this.now()),
      this.newId(),
    );
  }

  private set(changes: Partial<FlowView>): void {
    this.current = { ...this.current, ...changes };
    this.listeners.forEach((listener) => listener(this.current));
  }
}
