import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "#lib/api/client.ts";
import type { ScanEvent, ScanResult } from "#lib/phone/device-api.ts";
import { OfflineQueue } from "#lib/phone/queue.ts";
import {
  actionLabel,
  CHOICE_TIMEOUT_MS,
  feedbackText,
  LOOK_ONLY,
  refusalText,
  REPEAT_WINDOW_MS,
  RESULT_MS,
  ScanFlow,
} from "#lib/phone/scan-flow.ts";
import { PAIRING, tagRead } from "../../test/fake-bridge.ts";
import tags from "../../test/tags.json";

function result(fields: Partial<ScanResult> = {}): ScanResult {
  return {
    feedback: "ok",
    event_id: null,
    state: "sealed",
    product: {
      id: 1,
      display_name: "Black PLA Basic",
      filament_type: "PLA",
      color_rgba: "000000FF",
      material_id: "GFA00",
      variant_id: "A00-K00",
    },
    spool: {
      id: 7,
      state: "sealed",
      received_at: "2026-10-12T10:00:00Z",
      opened_at: null,
      emptied_at: null,
      remaining_pct: null,
    },
    actions: ["opened", "empty", "cancel"],
    suggested: "opened",
    placeholder: false,
    ...fields,
  };
}

const memory = () => {
  let text: string | null = null;
  return { load: async () => text, save: async (next: string) => void (text = next) };
};

let clock = 0;
let ids = 0;

async function setup(scan: (event: ScanEvent) => Promise<ScanResult>, records = true) {
  const api = { scan: vi.fn(scan), revert: vi.fn().mockResolvedValue({}) };
  const queue = await OfflineQueue.open(memory());
  const flow = new ScanFlow({
    api,
    queue,
    pairing: PAIRING,
    appVersion: "app-1",
    now: () => clock,
    newId: () => `event-${++ids}`,
    records: () => records,
  });
  return { api, queue, flow };
}

const blackTag = () => tagRead(tags[0].blocks);

beforeEach(() => {
  vi.useFakeTimers();
  clock = 1_000_000;
  ids = 0;
});

afterEach(() => vi.useRealTimers());

describe("scan flow", () => {
  it("looks a spool up, offers its actions and records the choice", async () => {
    const { api, flow } = await setup(async (event) =>
      event.action === "lookup"
        ? result()
        : result({ feedback: "ok", state: "open", event_id: event.event_id }),
    );
    const seen: string[] = [];
    flow.subscribe((view) => seen.push(view.phase));

    await flow.tapped(blackTag());
    expect(flow.view).toMatchObject({
      phase: "choosing",
      actions: ["opened", "empty", "cancel"],
      suggested: "opened",
      card: { name: "Black PLA Basic", state: "sealed", spoolId: 7, offline: false },
    });
    expect(api.scan.mock.calls[0][0]).toMatchObject({ action: "lookup", device_id: "phone-1" });

    await flow.choose("opened");
    expect(flow.view).toMatchObject({ phase: "result", message: "Recorded Opened.", tone: "ok" });
    expect(flow.view.last).toMatchObject({ action: "opened", eventId: "event-2", queued: false });
    expect(seen).toEqual(["idle", "looking_up", "choosing", "sending", "sending", "result"]);

    vi.advanceTimersByTime(RESULT_MS);
    expect(flow.view.phase).toBe("idle");
    expect(flow.view.last?.action).toBe("opened");
  });

  it("cancels with no event after 15 seconds without a choice", async () => {
    const { api, flow } = await setup(async () => result());
    await flow.tapped(blackTag());

    vi.advanceTimersByTime(CHOICE_TIMEOUT_MS - 1);
    expect(flow.view.phase).toBe("choosing");
    vi.advanceTimersByTime(1);
    expect(flow.view.phase).toBe("idle");
    await flow.choose("opened");
    expect(api.scan).toHaveBeenCalledTimes(1);
  });

  it("sends the same action for the same spool once within 30 seconds", async () => {
    const { api, flow } = await setup(async () => result());
    await flow.tapped(blackTag());
    await flow.choose("opened");

    clock += REPEAT_WINDOW_MS - 1;
    await flow.tapped(blackTag());
    await flow.choose("opened");
    expect(flow.view.message).toBe("Opened was already recorded.");
    expect(api.scan).toHaveBeenCalledTimes(3); // two lookups, one action

    clock += 1;
    await flow.tapped(blackTag());
    await flow.choose("opened");
    expect(api.scan).toHaveBeenCalledTimes(5);
  });

  it("cancel and info send nothing", async () => {
    const { api, flow } = await setup(async () => result({ actions: ["empty", "info", "cancel"] }));
    await flow.tapped(blackTag());
    await flow.choose("info");
    expect(flow.view.phase).toBe("result");

    flow.dismiss();
    await flow.tapped(blackTag());
    await flow.choose("cancel");
    expect(flow.view.phase).toBe("idle");
    expect(api.scan).toHaveBeenCalledTimes(2);
  });

  it("ignores a choice when nothing is offered, and a tap while busy", async () => {
    let answer: (value: ScanResult) => void = () => {};
    const { api, flow } = await setup(() => new Promise((resolve) => (answer = resolve)));
    await flow.choose("opened");

    const first = flow.tapped(blackTag());
    await flow.tapped(blackTag());
    answer(result());
    await first;
    expect(api.scan).toHaveBeenCalledTimes(1);
  });

  it("shows unreadable tags and server errors", async () => {
    const { flow } = await setup(async () => result({ feedback: "unreadable" }));
    await flow.tapped(blackTag());
    expect(flow.view).toMatchObject({ phase: "result", tone: "error", card: null });
    expect(flow.view.message).toMatch(/Couldn't read this tag/);
  });

  it("explains a revoked token or a scan from outside the LAN", async () => {
    const { flow } = await setup(() => Promise.reject(new ApiError(401, "no")));
    await flow.tapped(blackTag());
    expect(flow.view.message).toMatch(/Pair it again/);

    const other = await setup(() => Promise.reject(new ApiError(422, "bad")));
    await other.flow.tapped(blackTag());
    expect(other.flow.view.message).toBe("The server couldn't look up this spool.");
  });

  it("decodes the tag itself and queues the choice when the server is down", async () => {
    const { api, queue, flow } = await setup(() => Promise.reject(new ApiError(0, "down")));
    await flow.tapped(blackTag());

    expect(flow.view).toMatchObject({
      phase: "choosing",
      actions: ["received", "opened", "empty"],
      suggested: null,
      tone: "warn",
      card: { name: "PLA Basic #000000", colorRgba: "000000FF", offline: true },
    });
    await flow.choose("received");

    expect(api.scan).toHaveBeenCalledTimes(1);
    expect(queue.size).toBe(1);
    expect(flow.view.message).toMatch(/^Queued New/);
    expect(flow.view.last).toMatchObject({ queued: true, action: "received" });
  });

  it("says when an offline tag cannot be decoded either", async () => {
    const { flow } = await setup(() => Promise.reject(new ApiError(0, "down")));
    await flow.tapped(tagRead());
    expect(flow.view.message).toMatch(/couldn't be read on the phone/);
  });

  it("queues an action when the server goes away after the lookup", async () => {
    const { queue, flow } = await setup(async (event) => {
      if (event.action === "lookup") return result();
      throw new ApiError(503, "busy");
    });
    await flow.tapped(blackTag());
    await flow.choose("opened");
    expect(queue.size).toBe(1);
  });

  it("reports a refused action", async () => {
    const { flow } = await setup(async (event) => {
      if (event.action === "lookup") return result();
      throw new ApiError(403, "LAN only");
    });
    await flow.tapped(blackTag());
    await flow.choose("opened");
    expect(flow.view.message).toMatch(/home network/);

    const other = await setup(async (event) => {
      if (event.action === "lookup") return result();
      throw new ApiError(422, "bad");
    });
    await other.flow.tapped(blackTag());
    await other.flow.choose("opened");
    expect(other.flow.view.message).toBe("The server couldn't record that.");
  });

  it("says when the queue is full", async () => {
    const { queue, flow } = await setup(() => Promise.reject(new ApiError(0, "down")));
    vi.spyOn(queue, "add").mockResolvedValue(false);
    await flow.tapped(blackTag());
    await flow.choose("opened");
    expect(flow.view).toMatchObject({ tone: "error", message: expect.stringMatching(/full/) });
  });

  it("marks a flagged result as a warning", async () => {
    const { flow } = await setup(async (event) =>
      event.action === "lookup" ? result() : result({ feedback: "flagged" }),
    );
    await flow.tapped(blackTag());
    await flow.choose("empty");
    expect(flow.view).toMatchObject({
      tone: "warn",
      message: "Recorded Empty, flagged for review.",
    });
  });

  it("undoes the last scan on the server", async () => {
    const { api, flow } = await setup(async () => result());
    await flow.undoLast(); // nothing yet
    await flow.tapped(blackTag());
    await flow.choose("opened");

    await flow.undoLast();
    expect(api.revert).toHaveBeenCalledWith("event-2");
    expect(flow.view.message).toBe("Undid Opened.");
    expect(flow.view.last?.undone).toBe(true);

    await flow.undoLast();
    expect(api.revert).toHaveBeenCalledTimes(1);
  });

  it("takes a queued scan back out instead of reverting it", async () => {
    const { api, queue, flow } = await setup(() => Promise.reject(new ApiError(0, "down")));
    await flow.tapped(blackTag());
    await flow.choose("empty");

    await flow.undoLast();
    expect(queue.size).toBe(0);
    expect(api.revert).not.toHaveBeenCalled();
    expect(flow.view.message).toBe("Removed the queued Empty.");
  });

  it("reports a failed undo", async () => {
    const { api, flow } = await setup(async () => result());
    api.revert.mockRejectedValue(new ApiError(0, "down"));
    await flow.tapped(blackTag());
    await flow.choose("opened");

    await flow.undoLast();
    expect(flow.view).toMatchObject({ tone: "error", message: "Couldn't undo it. Try again." });
    expect(flow.view.last?.undone).toBe(false);
  });

  it("stops its timers", async () => {
    const { flow } = await setup(async () => result());
    const listener = vi.fn();
    flow.subscribe(listener);
    await flow.tapped(blackTag());
    flow.stop();
    listener.mockClear();
    vi.advanceTimersByTime(CHOICE_TIMEOUT_MS);
    expect(listener).not.toHaveBeenCalled();
  });

  it("says when the screen is back to waiting for a tap", async () => {
    const { flow } = await setup(async () => result());
    const never = new AbortController();
    await flow.whenIdle(never.signal); // already idle

    await flow.tapped(blackTag());
    let idle = false;
    const waiting = flow.whenIdle(never.signal).then(() => (idle = true));
    await flow.choose("opened");
    await Promise.resolve();
    expect(idle).toBe(false); // showing the result
    vi.advanceTimersByTime(RESULT_MS);
    await waiting;
    expect(idle).toBe(true);

    await flow.tapped(blackTag());
    const stop = new AbortController();
    const stopped = flow.whenIdle(stop.signal);
    stop.abort();
    await stopped;
    await flow.whenIdle(stop.signal); // already aborted
  });

  it("shows an unknown spool from its lookup", async () => {
    const { flow } = await setup(async () =>
      result({ product: null, spool: null, state: "unknown", suggested: "received" }),
    );
    await flow.tapped(blackTag());
    expect(flow.view.card).toMatchObject({ name: "Unknown spool", state: null, spoolId: null });
  });
});

describe("scan wording", () => {
  it("labels actions as on the scanner", () => {
    expect(
      ["received", "opened", "empty", "info", "cancel"].map((a) => actionLabel(a as never)),
    ).toEqual(["New", "Opened", "Empty", "Info", "Cancel"]);
  });

  it("words every feedback code", () => {
    expect(feedbackText("ok_created", "opened", "open")).toBe(
      "Added as a new spool and recorded Opened.",
    );
    expect(feedbackText("already_in_state", "opened", "open")).toBe(
      "Already open. Nothing changed.",
    );
    expect(feedbackText("error", "empty", "open")).toBe("The server couldn't record that.");
  });

  it("only explains refusals", () => {
    expect(refusalText(new Error("x"))).toBeNull();
    expect(refusalText(new ApiError(500, "x"))).toBeNull();
  });
});

describe("scan flow, for the screen", () => {
  it("starts a fresh countdown for each timer and names the outcome", async () => {
    const { flow } = await setup(async (event) =>
      event.action === "lookup" ? result({ actions: ["opened", "info", "cancel"] }) : result(),
    );

    await flow.tapped(blackTag());
    const choosing = flow.view.countdown;
    expect(choosing).toMatchObject({ ms: CHOICE_TIMEOUT_MS });
    expect(flow.view.outcome).toBeNull();

    await flow.choose("opened");
    expect(flow.view).toMatchObject({ outcome: "recorded", countdown: { ms: RESULT_MS } });
    expect(flow.view.countdown!.id).toBeGreaterThan(choosing!.id);

    flow.dismiss();
    expect(flow.view).toMatchObject({ phase: "idle", countdown: null, outcome: null });

    await flow.tapped(blackTag());
    await flow.choose("info");
    expect(flow.view).toMatchObject({ phase: "result", outcome: "info", countdown: null });
  });

  it("calls an unchanged state a notice, but keeps it for Undo", async () => {
    const { flow } = await setup(async (event) =>
      event.action === "lookup" ? result() : result({ feedback: "already_in_state" }),
    );
    await flow.tapped(blackTag());
    await flow.choose("opened");
    expect(flow.view.outcome).toBe("notice");
    expect(flow.view.last?.action).toBe("opened");
  });

  it("calls a queued choice queued, and an error a notice", async () => {
    const { flow } = await setup(async () => {
      throw new ApiError(0, "offline");
    });
    await flow.tapped(blackTag());
    await flow.choose("received");
    expect(flow.view.outcome).toBe("queued");

    const refused = await setup(async () => {
      throw new ApiError(403, "LAN only");
    });
    await refused.flow.tapped(blackTag());
    expect(refused.flow.view.outcome).toBe("notice");
  });

  it("tells whether the server answered", async () => {
    const reached: string[] = [];
    let mode: "up" | "down" | "refused" = "up";
    const api = {
      scan: vi.fn(async () => {
        if (mode === "down") throw new ApiError(0, "offline");
        if (mode === "refused") throw new ApiError(401, "token");
        return result();
      }),
      revert: vi.fn().mockResolvedValue({}),
    };
    const flow = new ScanFlow({
      api,
      queue: await OfflineQueue.open(memory()),
      pairing: PAIRING,
      appVersion: "app-1",
      onReach: (reach) => reached.push(reach),
    });

    await flow.tapped(blackTag());
    flow.dismiss();
    mode = "down";
    await flow.tapped(blackTag());
    flow.dismiss();
    mode = "refused";
    await flow.tapped(blackTag());

    expect(reached).toEqual(["online", "offline", "online"]); // a refusal is still an answer
  });
});

describe("scan flow, the last scan", () => {
  it("remembers the spool as the server now has it", async () => {
    const { flow } = await setup(async (event) =>
      event.action === "lookup"
        ? result({ spool: null, state: "unknown", actions: ["received", null, "cancel"] })
        : result({ feedback: "ok_created" }),
    );
    await flow.tapped(blackTag());
    expect(flow.view.card?.spoolId).toBeNull();

    await flow.choose("received");

    expect(flow.view.last?.card.spoolId).toBe(7);
  });

  it("keeps the card it had when the server names no product", async () => {
    const { flow } = await setup(async (event) =>
      event.action === "lookup" ? result() : result({ product: null }),
    );
    await flow.tapped(blackTag());
    await flow.choose("opened");
    expect(flow.view.last?.card.name).toBe("Black PLA Basic");
  });

  it("shows a Viewer's phone the spool, with nothing to record", async () => {
    const { flow } = await setup(
      async () => result({ actions: ["info", null, "cancel"], suggested: null }),
      false,
    );
    await flow.tapped(blackTag());

    expect(flow.view).toMatchObject({
      phase: "choosing",
      actions: ["info", null, "cancel"],
      suggested: null,
      message: LOOK_ONLY,
      card: { name: "Black PLA Basic" },
    });
  });

  it("offers a Viewer's phone nothing to queue when the server is down", async () => {
    const { flow, queue } = await setup(() => Promise.reject(new ApiError(0, "down")), false);
    await flow.tapped(blackTag());

    expect(flow.view).toMatchObject({
      phase: "choosing",
      actions: [null, null, "cancel"],
      message: `Can't reach the server. ${LOOK_ONLY}`,
      card: { offline: true },
    });
    expect(queue.size).toBe(0);
  });

  it("explains a refusal to a phone whose user became a Viewer", () => {
    const refused = new ApiError(
      403,
      "this phone's account can look spools up but not record them",
    );
    expect(refusalText(refused)).toBe(LOOK_ONLY);
  });
});
