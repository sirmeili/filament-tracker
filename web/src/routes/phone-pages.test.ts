import { cleanup, render, screen, waitFor, within } from "@testing-library/svelte";
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
const AccountPage = (await import("./account/+page.svelte")).default;
const LoginPage = (await import("./login/+page.svelte")).default;

const children = createRawSnippet(() => ({ render: () => "<p>page content</p>" }));
const CODE = JSON.stringify({ v: 1, url: PAIRING.url, token: PAIRING.token, device_id: "phone-1" });

let native: FakeBridge;
let server: ReturnType<typeof fakeFetch>;
let serverUp = true;
let unlinkStatus = 204;

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
  unlinkStatus = 204;
  server = fakeFetch({
    "POST /api/v1/devices/unlink": () =>
      serverUp ? { status: unlinkStatus } : new TypeError("down"),
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

    expect(await screen.findByRole("link", { name: "Scan" })).toHaveAttribute("href", "/scan");
    expect(screen.getByText("page content")).toBeInTheDocument();
    session.user = null;
  });

  it("offers Pairing when the paired server cannot be reached", async () => {
    await paired();
    session.loaded = false;
    const load = vi.spyOn(session, "load").mockRejectedValue(new TypeError("down"));
    at("/spools");

    render(Layout, { children });

    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server.");
    expect(screen.getByRole("link", { name: "Phone pairing" })).toHaveAttribute("href", "/pair");
    load.mockRestore();
  });

  it("shows Pairing at /pair without the server or a sign-in", async () => {
    await paired();
    session.loaded = false;
    const load = vi.spyOn(session, "load");
    at("/pair");

    render(Layout, { children });

    expect(await screen.findByText("page content")).toBeInTheDocument();
    expect(load).not.toHaveBeenCalled();
    load.mockRestore();
  });
});

describe("sign-in page in the phone app", () => {
  it("links to the phone's pairing, only in the app", () => {
    const app = render(LoginPage);
    expect(screen.getByRole("link", { name: "Phone pairing" })).toHaveAttribute("href", "/pair");
    app.unmount();

    setBridge(browserBridge);
    render(LoginPage);
    expect(screen.queryByRole("link", { name: "Phone pairing" })).toBeNull();
  });
});

describe("account page in the phone app", () => {
  it("links to the phone's pairing, only in the app", () => {
    const app = render(AccountPage);
    expect(screen.getByRole("link", { name: "Phone pairing" })).toHaveAttribute("href", "/pair");
    app.unmount();

    setBridge(browserBridge);
    render(AccountPage);
    expect(screen.queryByRole("link", { name: "Phone pairing" })).toBeNull();
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
  }, 15_000); // types a full token

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

  it("unlinks after confirming, warning about queued scans, and revokes the token", async () => {
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
    expect(screen.getByRole("alert")).toHaveTextContent("Unlinking drops them");
    await userEvent.click(screen.getByRole("button", { name: "Unlink this phone" }));
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(server.calls.some((call) => call.url.endsWith("/devices/unlink"))).toBe(false);
    await userEvent.click(screen.getByRole("button", { name: "Unlink this phone" }));
    const confirm = screen.getByRole("group", { name: "Confirm" });
    expect(confirm).toHaveAccessibleDescription(/revokes this phone's token/);
    await userEvent.click(within(confirm).getByRole("button", { name: "Unlink this phone" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "This phone is unlinked, and its token was revoked on the server.",
    );
    expect(phone.paired).toBe(false);
    const call = server.calls.find((c) => c.url.endsWith("/api/v1/devices/unlink"))!;
    expect(call.url).toBe(PAIRING.url + "/api/v1/devices/unlink");
    expect(new Headers(call.init.headers).get("Authorization")).toBe(`Bearer ${PAIRING.token}`);
    expect(screen.getByRole("button", { name: "Scan pairing code" })).toBeInTheDocument();
    expect(await native.secureGet("pairing")).toBeNull();
    expect(await native.secureGet("kdf_salt")).toBeNull();
  });

  async function unlinkFromPairPage(): Promise<void> {
    render(PairPage);
    await userEvent.click(screen.getByRole("button", { name: "Unlink this phone" }));
    const confirm = screen.getByRole("group", { name: "Confirm" });
    await userEvent.click(within(confirm).getByRole("button", { name: "Unlink this phone" }));
  }

  it("unlinks a phone whose server cannot be reached, saying it is still listed", async () => {
    await paired();
    serverUp = false;

    await unlinkFromPairPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "the server could not be reached, so its token still works there",
    );
    expect(phone.paired).toBe(false);
    expect(await native.secureGet("pairing")).toBeNull();
  });

  it("counts a token the server already refuses as revoked", async () => {
    await paired();
    unlinkStatus = 401;

    await unlinkFromPairPage();

    expect(await screen.findByRole("status")).toHaveTextContent("its token was revoked");
  });

  it("does not count other refusals as revoked", async () => {
    await paired();
    unlinkStatus = 403;

    await unlinkFromPairPage();

    expect(await screen.findByRole("alert")).toHaveTextContent("still works there");
    expect(phone.paired).toBe(false);
  });
});

describe("scan page", () => {
  it("looks up a tapped spool and records the chosen action", async () => {
    await paired();
    render(ScanPage);
    expect(await screen.findByText("Hold a spool to the back of your phone")).toBeInTheDocument();

    native.tap(tagRead(tags[0].blocks));

    const card = await screen.findByRole("article", { name: "Spool" });
    expect(card).toHaveTextContent("Black PLA Basic");
    expect(card).toHaveTextContent("Sealed");
    expect(card).toHaveTextContent("Received Oct 12 · #7");
    expect(screen.getByText("Pick within 15 s")).toBeInTheDocument();
    const opened = screen.getByRole("button", { name: "Opened" });
    expect(opened).toHaveClass("primary");
    expect(opened).toHaveAccessibleDescription("Suggested");
    expect(screen.getByRole("button", { name: "Empty" })).not.toHaveAccessibleDescription();

    await userEvent.click(opened);
    expect(await screen.findByRole("heading", { name: "Opened" })).toBeInTheDocument();
    expect(screen.getByText("Recorded just now · spool #7")).toBeInTheDocument();
    expect(screen.getByText("Ready for the next spool in 3 s")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View spool" })).toHaveAttribute("href", "/spools/7");
    await userEvent.click(screen.getByRole("button", { name: "Scan next" }));
    expect(screen.getByText("Last scan")).toBeInTheDocument();
    expect(screen.getByText(/Black PLA Basic · Opened/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Undo" }));
    expect(await screen.findByText(/\(undone\)/)).toBeInTheDocument();
    expect(server.calls.some((c) => c.url.endsWith("/revert"))).toBe(true);
  });

  it("queues a choice when the server is down and shows the queue", async () => {
    await paired();
    serverUp = false;
    render(ScanPage);
    await screen.findByText("Hold a spool to the back of your phone");

    native.tap(tagRead(tags[0].blocks));
    expect(await screen.findByText(/Your choice will be queued/)).toBeInTheDocument();
    expect(screen.getByRole("article", { name: "Spool" })).toHaveTextContent("PLA Basic #000000");
    await userEvent.click(screen.getByRole("button", { name: "New" }));

    expect(await screen.findByRole("heading", { name: "New" })).toBeInTheDocument();
    expect(screen.getByText(/Queued · it will be sent/)).toBeInTheDocument();
    expect(screen.getByText("Offline · 1 queued")).toBeInTheDocument();
  });

  it("keeps listening after a tag is pulled away", async () => {
    await paired();
    render(ScanPage);
    await screen.findByText("Hold a spool to the back of your phone");
    const before = native.reads;

    native.fail();

    await waitFor(() => expect(native.reads).toBe(before + 1));
  });

  it("reads one spool at a time, listening again once it is dealt with", async () => {
    await paired();
    render(ScanPage);
    await screen.findByText("Hold a spool to the back of your phone");
    expect(native.reads).toBe(1);

    native.tap(tagRead(tags[0].blocks));
    await userEvent.click(await screen.findByRole("button", { name: "Opened" }));
    await screen.findByText("Recorded just now · spool #7");
    expect(native.reads).toBe(1); // not listening while the spool is on screen

    await userEvent.click(screen.getByRole("button", { name: "Scan next" }));
    await waitFor(() => expect(native.reads).toBe(2));
  });

  it("notices NFC being turned on without a restart", async () => {
    native.status = "nfc_off";
    await paired();
    render(ScanPage);
    expect(await screen.findByRole("alert")).toHaveTextContent(/NFC/);

    native.status = "ready";
    document.dispatchEvent(new Event("visibilitychange")); // back from Android settings
    expect(await screen.findByText("Hold a spool to the back of your phone")).toBeInTheDocument();
  });

  it("starts a fresh read when the app comes back to the front", async () => {
    await paired();
    render(ScanPage);
    await screen.findByText("Hold a spool to the back of your phone");

    document.dispatchEvent(new Event("visibilitychange"));

    await waitFor(() => expect(native.reads).toBe(2));
  });

  it("explains a phone that cannot read Bambu tags", async () => {
    native.status = "no_mifare";
    await paired();
    render(ScanPage);

    expect(await screen.findByRole("alert")).toHaveTextContent(/MIFARE Classic/);
  });

  it("shows Online once the server answers", async () => {
    await paired();
    render(ScanPage);
    expect(await screen.findByText("Online")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open the full app" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Phone pairing" })).toHaveAttribute("href", "/pair");
    expect(screen.getByRole("group", { name: "Theme" })).toBeInTheDocument();
  });

  it("restarts the countdown bar for each spool", async () => {
    await paired();
    render(ScanPage);
    await screen.findByText("Hold a spool to the back of your phone");
    const bar = () => document.querySelector(".fill") as HTMLElement;

    native.tap(tagRead(tags[0].blocks));
    await screen.findByText("Pick within 15 s");
    const first = bar();
    expect(first.dataset.ms).toBe("15000");
    expect(first.style.animationDuration).toBe("15000ms");
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    await waitFor(() => expect(native.reads).toBe(2));
    native.tap(tagRead(tags[0].blocks));
    await screen.findByText("Pick within 15 s");
    expect(bar()).not.toBe(first);
  });

  it("shows a message when the server refuses, with Scan next", async () => {
    await paired();
    server = fakeFetch({
      "POST /api/v1/devices/heartbeat": () => ({ status: 204 }),
      "POST /api/v1/scans": () => ({ status: 403, body: { detail: "LAN only" } }),
    });
    vi.stubGlobal("fetch", server);
    render(ScanPage);
    await screen.findByText("Hold a spool to the back of your phone");

    native.tap(tagRead(tags[0].blocks));

    expect(await screen.findByText(/only from your home network/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "View spool" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Scan next" }));
    expect(screen.getByText("Hold a spool to the back of your phone")).toBeInTheDocument();
  });

  it("waits for the session before listening", () => {
    render(ScanPage);
    expect(screen.getByText("Starting…")).toBeInTheDocument();
    expect(native.reads).toBe(0);
  });
});

describe("scan page, unpacking a delivery", () => {
  afterEach(() => {
    phone.delivery.clear();
    phone.delivery.on = false;
  });

  async function deliveryOn(): Promise<void> {
    await paired();
    render(ScanPage);
    await screen.findByText("Hold a spool to the back of your phone");
    await userEvent.click(screen.getByRole("button", { name: "Delivery" }));
  }

  it("lists each spool recorded, with totals, and undoes only the newest", async () => {
    await deliveryOn();
    expect(screen.getByRole("button", { name: "Delivery" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByText("Spools you scan show up here.")).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Clear" })).toBeNull();

    native.tap(tagRead(tags[0].blocks));
    const panel = await screen.findByRole("region", { name: "Scanned spool" });
    expect(within(panel).getByRole("article", { name: "Spool" })).toHaveTextContent(
      "Received Oct 12 · #7",
    );
    expect(screen.queryByRole("button", { name: "Delivery" })).toBeNull(); // not mid-choice
    await userEvent.click(within(panel).getByRole("button", { name: "Opened" }));

    expect(await screen.findByText("Recorded Opened")).toBeInTheDocument();
    const list = screen.getByRole("list", { name: "Spools in this delivery" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(1);
    expect(within(list).getByRole("listitem")).toHaveClass("fresh");
    expect(screen.getAllByRole("button", { name: "Undo" })).toHaveLength(1); // the panel's
    expect(screen.getByText("0 new · 1 opened")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Scan next" }));
    expect(within(list).getByRole("listitem")).not.toHaveClass("fresh");

    native.tap(tagRead(tags[0].blocks));
    const again = await screen.findByRole("region", { name: "Scanned spool" });
    await userEvent.click(within(again).getByRole("button", { name: "Empty" }));
    await screen.findByText("Recorded Empty");
    await userEvent.click(screen.getByRole("button", { name: "Scan next" }));

    const rows = within(list).getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).queryByRole("button", { name: "Undo" })).toBeNull();
    await userEvent.click(within(rows[1]).getByRole("button", { name: "Undo" }));
    expect(await within(rows[1]).findByText("Undone")).toBeInTheDocument();
    expect(screen.getByText("0 new · 1 opened")).toBeInTheDocument();
  });

  it("keeps the list after leaving Scan, until Clear", async () => {
    await deliveryOn();
    native.tap(tagRead(tags[0].blocks));
    const panel = await screen.findByRole("region", { name: "Scanned spool" });
    await userEvent.click(within(panel).getByRole("button", { name: "Opened" }));
    await screen.findByText("Recorded Opened");
    await userEvent.click(screen.getByRole("button", { name: "Undo" }));
    await screen.findByText("Undone");
    cleanup();

    render(ScanPage);
    const list = await screen.findByRole("list", { name: "Spools in this delivery" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(1);

    await userEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(screen.getByText("Spools you scan show up here.")).toBeInTheDocument();
  });

  it("marks a queued spool until it is sent, and turns off again", async () => {
    await paired();
    serverUp = false;
    render(ScanPage);
    await screen.findByText("Hold a spool to the back of your phone");
    await userEvent.click(screen.getByRole("button", { name: "Delivery" }));

    native.tap(tagRead(tags[0].blocks));
    const panel = await screen.findByRole("region", { name: "Scanned spool" });
    await userEvent.click(within(panel).getByRole("button", { name: "New" }));
    expect(await screen.findByText("Queued New")).toBeInTheDocument();
    expect(screen.getByText(/· queued/)).toBeInTheDocument();

    serverUp = true;
    await phone.session!.retry(true);
    await waitFor(() => expect(screen.queryByText(/· queued/)).toBeNull());

    await userEvent.click(screen.getByRole("button", { name: "Scan next" }));
    await userEvent.click(screen.getByRole("button", { name: "Delivery" }));
    expect(await screen.findByText("Hold a spool to the back of your phone")).toBeInTheDocument();
  });

  it("shows a refusal in the panel", async () => {
    await paired();
    vi.stubGlobal(
      "fetch",
      fakeFetch({
        "POST /api/v1/devices/heartbeat": () => ({ status: 204 }),
        "POST /api/v1/scans": () => ({ status: 403 }),
      }),
    );
    render(ScanPage);
    await screen.findByText("Hold a spool to the back of your phone");
    await userEvent.click(screen.getByRole("button", { name: "Delivery" }));

    native.tap(tagRead(tags[0].blocks));

    expect(await screen.findByText(/only from your home network/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Scan next" }));
    expect(screen.getByText("Ready")).toBeInTheDocument();
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
