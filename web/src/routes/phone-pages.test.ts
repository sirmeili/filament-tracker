import { render, screen, waitFor, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { createRawSnippet } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Me } from "#lib/api/types.ts";
import { browserBridge, setBridge } from "#lib/phone/bridge.ts";
import { savePairing } from "#lib/phone/pairing-store.ts";
import { fakeBridge, fakeFetch, PAIRING, tagRead, type FakeBridge } from "../test/fake-bridge.ts";
import tags from "../test/tags.json";

const nav = vi.hoisted(() => ({
  page: { url: new URL("https://localhost/") },
  goto: vi.fn(),
}));
vi.mock("$app/state", () => ({ page: nav.page }));
vi.mock("$app/navigation", () => ({ goto: nav.goto }));

const { session } = await import("#lib/auth/session.svelte.ts");
const { phone } = await import("#lib/phone/phone-state.svelte.ts");
const Layout = (await import("./+layout.svelte")).default;
const ScanPage = (await import("./scan/+page.svelte")).default;
const PairPage = (await import("./pair/+page.svelte")).default;

const children = createRawSnippet(() => ({ render: () => "<p>page content</p>" }));
const CODE = JSON.stringify({ v: 1, url: PAIRING.url, token: PAIRING.token, device_id: "phone-1" });

let native: FakeBridge;
let server: ReturnType<typeof fakeFetch>;
let serverUp = true;

function at(path: string): void {
  nav.page.url = new URL(path, "https://localhost");
}

function lookup(fields: Record<string, unknown> = {}) {
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

async function paired(): Promise<void> {
  await savePairing(PAIRING, "AABB");
  await phone.load();
}

beforeEach(() => {
  native = fakeBridge();
  setBridge(native);
  nav.goto.mockReset();
  serverUp = true;
  server = fakeFetch({
    "GET /api/v1/devices/provisioning": () => ({ status: 200, body: { kdf_salt: "AABB" } }),
    "POST /api/v1/devices/heartbeat": () => (serverUp ? { status: 204 } : new TypeError("down")),
    "POST /api/v1/scans": (body) => {
      if (!serverUp) return new TypeError("down");
      const action = (body as { action: string }).action;
      return {
        status: 200,
        body:
          action === "lookup" ? lookup() : lookup({ state: "open", actions: [], suggested: null }),
      };
    },
    "POST /api/v1/events/": () => ({ status: 200, body: {} }),
  });
  vi.stubGlobal("fetch", server);
});

afterEach(async () => {
  setBridge(native);
  await phone.unpair();
  phone.loaded = false;
  setBridge(browserBridge);
  vi.unstubAllGlobals();
});

describe("layout in the phone app", () => {
  it("sends an unpaired phone to Pairing, without signing in", async () => {
    session.loaded = false;
    const load = vi.spyOn(session, "load");
    at("/");

    render(Layout, { children });

    await waitFor(() => expect(nav.goto).toHaveBeenCalledWith("/pair", { replaceState: true }));
    expect(await screen.findByText("page content")).toBeInTheDocument();
    expect(load).not.toHaveBeenCalled();
  });

  it("opens a paired phone on Scan", async () => {
    await savePairing(PAIRING, "AABB");
    at("/");

    render(Layout, { children });

    await waitFor(() => expect(nav.goto).toHaveBeenCalledWith("/scan", { replaceState: true }));
  });

  it("shows the full web app with a way back to Scan", async () => {
    await paired();
    session.user = { id: 1, username: "frank", role: "viewer" } as Me;
    session.loaded = true;
    at("/spools");

    render(Layout, { children });

    expect(await screen.findByRole("link", { name: "Back to Scan" })).toHaveAttribute(
      "href",
      "/scan",
    );
    expect(screen.getByText("page content")).toBeInTheDocument();
    session.user = null;
  });
});

describe("pairing page", () => {
  it("pairs by scanning the code from the Devices page", async () => {
    native.qr.push(CODE);
    render(PairPage);

    await userEvent.click(screen.getByRole("button", { name: "Scan pairing code" }));

    await waitFor(() => expect(nav.goto).toHaveBeenCalledWith("/scan"));
    expect(phone.paired).toBe(true);
    expect(native.storage.get("kdf_salt")).toBe("AABB");
    expect(server.calls[0].url).toBe("https://filament.example.com/api/v1/devices/provisioning");
  });

  it("says what is wrong with a scanned code, or with the camera", async () => {
    native.qr.push("hello", null, new Error("no camera"));
    render(PairPage);
    const scan = screen.getByRole("button", { name: "Scan pairing code" });

    await userEvent.click(scan);
    expect(screen.getByRole("alert")).toHaveTextContent(/not a Filament Tracker pairing code/);
    await userEvent.click(scan); // backed out: nothing happens
    expect(screen.queryByRole("alert")).toBeNull();
    await userEvent.click(scan);
    expect(screen.getByRole("alert")).toHaveTextContent(/camera could not be opened/);
  });

  it("pairs with typed details", async () => {
    render(PairPage);
    await userEvent.click(screen.getByRole("button", { name: "Type the details instead" }));
    await userEvent.type(screen.getByLabelText("Server address"), "filament");
    await userEvent.click(screen.getByRole("button", { name: "Pair" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/full address/);

    await userEvent.clear(screen.getByLabelText("Server address"));
    await userEvent.type(screen.getByLabelText("Server address"), PAIRING.url);
    await userEvent.type(screen.getByLabelText("Device ID"), "phone-1");
    await userEvent.type(screen.getByLabelText("Token"), PAIRING.token);
    await userEvent.click(screen.getByRole("button", { name: "Pair" }));

    await waitFor(() => expect(phone.paired).toBe(true));
  });

  it("explains a server that has no tag key constant", async () => {
    vi.stubGlobal(
      "fetch",
      fakeFetch({ "GET /api/v1/devices/provisioning": () => ({ status: 503 }) }),
    );
    native.qr.push(CODE);
    render(PairPage);

    await userEvent.click(screen.getByRole("button", { name: "Scan pairing code" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/BAMBU_KDF_SALT/);
    expect(phone.paired).toBe(false);
  });

  it("forgets the pairing after confirming, warning about queued scans", async () => {
    await paired();
    await phone.session!.queue.add({
      event_id: "e",
      device_id: "phone-1",
      action: "opened",
      tag_uid: "01020304",
      blocks: [],
      read_ok: true,
      scanned_at: new Date().toISOString(),
      fw_version: "1",
    });
    render(PairPage);

    expect(screen.getByText(/filament\.example\.com/)).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("1 queued scans have not been sent yet");
    await userEvent.click(screen.getByRole("button", { name: "Forget pairing" }));
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await userEvent.click(screen.getByRole("button", { name: "Forget pairing" }));
    await userEvent.click(
      within(screen.getByRole("group", { name: "Confirm" })).getByRole("button", {
        name: "Forget pairing",
      }),
    );

    expect(phone.paired).toBe(false);
    expect(await screen.findByRole("button", { name: "Scan pairing code" })).toBeInTheDocument();
  });
});

describe("scan page", () => {
  it("looks up a tapped spool and records the chosen action", async () => {
    await paired();
    render(ScanPage);
    expect(await screen.findByText("Tap a spool on the back of the phone.")).toBeInTheDocument();

    native.tap(tagRead(tags[0].blocks));

    const card = await screen.findByRole("article", { name: "Spool" });
    expect(card).toHaveTextContent("Black PLA Basic");
    expect(card).toHaveTextContent("Sealed, received Oct 12");
    expect(within(card).getByRole("link")).toHaveAttribute("href", "/spools/7");
    const opened = screen.getByRole("button", { name: "Opened" });
    expect(opened).toHaveClass("primary");
    expect(screen.getByText("Highlighted: the suggested action")).toBeInTheDocument();

    await userEvent.click(opened);
    expect(await screen.findByText("Recorded Opened.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(screen.getByText(/Last scan: Black PLA Basic/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Undo" }));
    expect(await screen.findByText(/\(undone\)/)).toBeInTheDocument();
    expect(server.calls.some((c) => c.url.endsWith("/revert"))).toBe(true);
  });

  it("queues a choice when the server is down and shows the queue", async () => {
    await paired();
    serverUp = false;
    render(ScanPage);
    await screen.findByText("Tap a spool on the back of the phone.");

    native.tap(tagRead(tags[0].blocks));
    expect(await screen.findByText(/Your choice will be queued/)).toBeInTheDocument();
    expect(screen.getByRole("article", { name: "Spool" })).toHaveTextContent("PLA Basic #000000");
    await userEvent.click(screen.getByRole("button", { name: "New" }));

    expect(await screen.findByText("1 queued")).toBeInTheDocument();
  });

  it("keeps listening after a tag is pulled away", async () => {
    await paired();
    render(ScanPage);
    await screen.findByText("Tap a spool on the back of the phone.");
    const before = native.reads;

    native.fail();

    await waitFor(() => expect(native.reads).toBe(before + 1));
  });

  it("explains a phone that cannot read Bambu tags", async () => {
    native.status = "no_mifare";
    await paired();
    render(ScanPage);

    expect(await screen.findByRole("alert")).toHaveTextContent(/MIFARE Classic/);
  });

  it("waits for the session before listening", () => {
    render(ScanPage);
    expect(screen.getByText("Starting…")).toBeInTheDocument();
    expect(native.reads).toBe(0);
  });
});

describe("phone pages in a browser", () => {
  it("say they belong to the app", () => {
    setBridge(browserBridge);
    render(ScanPage);
    expect(
      screen.getByText(/Scanning works in the Filament Tracker Android app/),
    ).toBeInTheDocument();
    render(PairPage);
    expect(screen.getByText(/Pairing is for the Filament Tracker Android app/)).toBeInTheDocument();
    setBridge(native);
  });
});
