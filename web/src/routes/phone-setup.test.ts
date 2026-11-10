// Setting a phone up by signing in, its opening screen, and a Viewer's phone (Pairing and
// Phone scanner in docs/SPEC.md).
import { cleanup, render, screen, waitFor, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { createRawSnippet } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiUrl } from "#lib/api/client.ts";
import type { Me } from "#lib/api/types.ts";
import { browserBridge, setBridge } from "#lib/phone/bridge.ts";
import { saveOpenOn, savePairing, saveServer } from "#lib/phone/pairing-store.ts";
import { fakeBridge, fakeFetch, PAIRING, type FakeBridge } from "../test/fake-bridge.ts";

const nav = vi.hoisted(() => ({
  page: { url: new URL("https://localhost/") },
  goto: vi.fn(),
}));
vi.mock("$app/state", () => ({ page: nav.page }));
vi.mock("$app/navigation", () => ({ goto: nav.goto }));

const { session } = await import("#lib/auth/session.svelte.ts");
const { phone } = await import("#lib/phone/phone-state.svelte.ts");
const Layout = (await import("./+layout.svelte")).default;
const PairPage = (await import("./pair/+page.svelte")).default;
const LoginPage = (await import("./login/+page.svelte")).default;

const children = createRawSnippet(() => ({ render: () => "<p>page content</p>" }));
const BOB = { id: 2, username: "bob", role: "viewer", time_zone: "UTC" } as Me;

let native: FakeBridge;
let server: ReturnType<typeof fakeFetch>;
let mine: () => { status: number; body?: unknown; headers?: Record<string, string> } | Error;

function at(path: string): void {
  nav.page.url = new URL(path, "https://localhost");
}

function signedIn(user: Me | null): void {
  session.user = user;
  session.loaded = true;
}

beforeEach(() => {
  native = fakeBridge();
  setBridge(native);
  nav.goto.mockReset();
  mine = () => ({ status: 201, body: { id: "phone-ab12cd34", token: PAIRING.token } });
  server = fakeFetch({
    "POST /api/v1/devices/mine": () => mine(),
    "GET /api/v1/devices/provisioning": () => ({
      status: 200,
      body: { kdf_salt: "AABB", access: null, records: false },
    }),
    "POST /api/v1/devices/heartbeat": () => ({ status: 204 }),
    "POST /api/v1/auth/logout": () => ({ status: 204 }),
    "POST /api/v1/devices/unlink": () => ({ status: 204 }),
  });
  vi.stubGlobal("fetch", server);
});

afterEach(async () => {
  cleanup();
  setBridge(native);
  await phone.unpair();
  phone.loaded = false;
  session.user = null;
  session.loaded = false;
  setBridge(browserBridge);
  vi.unstubAllGlobals();
});

describe("first start: the server's address", () => {
  it("checks the address, keeps it and goes to sign in", async () => {
    await phone.load();
    render(PairPage);
    expect(screen.getByRole("heading", { name: "Set up this phone" })).toBeInTheDocument();
    const address = screen.getByLabelText("Server address");

    await userEvent.type(address, "rollcall");
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/full address/);
    expect(nav.goto).not.toHaveBeenCalled();

    await userEvent.clear(address);
    await userEvent.type(address, "https://rollcall.example.com/");
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() => expect(nav.goto).toHaveBeenCalledWith("/login"));
    expect(phone.server).toBe("https://rollcall.example.com");
    expect(await native.secureGet("server")).toBe("https://rollcall.example.com");
    expect(apiUrl("/auth/me")).toBe("https://rollcall.example.com/api/v1/auth/me");
  });

  it("offers pairing with a code, and going back", async () => {
    await phone.load();
    render(PairPage);

    await userEvent.click(screen.getByRole("button", { name: "Pair with a code instead" }));
    expect(screen.getByRole("button", { name: "Scan pairing code" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Sign in instead" }));
    expect(screen.getByLabelText("Server address")).toBeInTheDocument();
  });

  it("remembers the chosen server when the app opens again", async () => {
    await saveServer("https://rollcall.example.com");

    await phone.load();

    expect(phone.server).toBe("https://rollcall.example.com");
    expect(phone.paired).toBe(false);
    expect(apiUrl("/x")).toBe("https://rollcall.example.com/api/v1/x");
  });
});

describe("setting the phone up after signing in", () => {
  beforeEach(async () => {
    await saveServer(PAIRING.url);
    await phone.load();
  });

  it("asks a signed-out user to sign in, or to use a different server", async () => {
    signedIn(null);
    render(PairPage);

    expect(screen.getByText(PAIRING.url)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");

    await userEvent.click(screen.getByRole("button", { name: "Use a different server" }));

    await waitFor(() => expect(phone.server).toBeNull());
    expect(session.loaded).toBe(false);
    expect(await native.secureGet("server")).toBeNull();
    expect(screen.getByLabelText("Server address")).toBeInTheDocument();
  });

  it("waits for the sign-in check", () => {
    session.loaded = false;
    render(PairPage);
    expect(screen.getByRole("status")).toHaveTextContent("Checking with the server");
  });

  it("sets the phone up as the user's own, then asks where it opens", async () => {
    signedIn(BOB);
    render(PairPage);

    expect(
      await screen.findByRole("heading", { name: "This phone is set up" }),
    ).toBeInTheDocument();
    expect(phone.paired).toBe(true);
    expect(phone.server).toBeNull();
    expect(phone.session!.pairing).toEqual({
      url: PAIRING.url,
      token: PAIRING.token,
      deviceId: "phone-ab12cd34",
    });
    expect(phone.session!.records).toBe(false);
    expect(await native.secureGet("records")).toBe("false");
    const call = server.calls.find((c) => c.url.endsWith("/devices/mine"))!;
    expect(call.url).toBe(PAIRING.url + "/api/v1/devices/mine");
    expect(new Headers(call.init.headers).get("X-Requested-With")).toBe("filament-tracker");
    expect(JSON.parse(String(call.init.body))).toEqual({ name: expect.any(String) });

    const choices = screen.getByRole("group", { name: "This phone opens on" });
    await userEvent.click(within(choices).getByRole("button", { name: /Looking at stock/ }));

    await waitFor(() => expect(nav.goto).toHaveBeenCalledWith("/"));
    expect(phone.openOn).toBe("stock");
    expect(await native.secureGet("open_on")).toBe("stock");
  });

  it("opens on Scan when chosen", async () => {
    signedIn(BOB);
    render(PairPage);
    const choices = await screen.findByRole("group", { name: "This phone opens on" });

    await userEvent.click(within(choices).getByRole("button", { name: /Scanning/ }));

    await waitFor(() => expect(nav.goto).toHaveBeenCalledWith("/scan"));
    expect(phone.openOn).toBe("scan");
  });

  it("says to finish at home when away, and tries again", async () => {
    mine = () => ({
      status: 403,
      body: { detail: "phones can be set up only on the home network" },
      headers: { "X-Rollcall-Refused": "local-network-only" },
    });
    signedIn(BOB);
    render(PairPage);

    expect(await screen.findByRole("alert")).toHaveTextContent("Finish setting up at home");
    expect(phone.paired).toBe(false);

    mine = () => ({ status: 201, body: { id: "phone-ab12cd34", token: PAIRING.token } });
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(
      await screen.findByRole("heading", { name: "This phone is set up" }),
    ).toBeInTheDocument();
  });

  it("explains other failures", async () => {
    mine = () => ({ status: 409, body: { detail: "you already have 5 phones set up" } });
    signedIn(BOB);
    render(PairPage);

    expect(await screen.findByRole("alert")).toHaveTextContent("you already have 5 phones");
  });

  it("names the server on the sign-in page, with a way back", () => {
    render(LoginPage);
    expect(screen.getByText(PAIRING.url)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Use a different server" })).toHaveAttribute(
      "href",
      "/pair",
    );
  });
});

describe("layout while setting up", () => {
  it("signs in to the chosen server instead of sending the phone to Pairing", async () => {
    await saveServer(PAIRING.url);
    session.loaded = false;
    const load = vi.spyOn(session, "load").mockImplementation(async () => {
      session.loaded = true;
    });
    at("/login");

    render(Layout, { children });

    await waitFor(() => expect(load).toHaveBeenCalled());
    expect(nav.goto).not.toHaveBeenCalledWith("/pair", { replaceState: true });
    load.mockRestore();
  });

  it("sends a signed-in user to finish setting the phone up", async () => {
    await saveServer(PAIRING.url);
    signedIn(BOB);
    at("/");

    render(Layout, { children });

    await waitFor(() => expect(nav.goto).toHaveBeenCalledWith("/pair", { replaceState: true }));
  });

  it("checks the sign-in on Pairing too", async () => {
    await saveServer(PAIRING.url);
    session.loaded = false;
    const load = vi.spyOn(session, "load").mockImplementation(async () => {
      session.loaded = true;
    });
    at("/pair");

    render(Layout, { children });

    await waitFor(() => expect(load).toHaveBeenCalled());
    load.mockRestore();
  });

  it("opens a phone set to Looking at stock on Inventory", async () => {
    await savePairing(PAIRING, "AABB");
    await saveOpenOn("stock");
    signedIn(BOB);
    at("/");

    render(Layout, { children });

    expect(await screen.findByText("page content")).toBeInTheDocument();
    expect(nav.goto).not.toHaveBeenCalledWith("/scan", { replaceState: true });
  });
});

describe("a set-up phone on the Pairing page", () => {
  it("changes where it opens", async () => {
    await savePairing(PAIRING, "AABB");
    await phone.load();
    render(PairPage);
    const choices = screen.getByRole("group", { name: "This phone opens on" });
    // A phone paired with a code opens on Scan until changed.
    expect(within(choices).getByRole("button", { name: /Scanning/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    await userEvent.click(within(choices).getByRole("button", { name: /Looking at stock/ }));

    await waitFor(() => expect(phone.openOn).toBe("stock"));
    expect(within(choices).getByRole("button", { name: /Looking at stock/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(nav.goto).not.toHaveBeenCalled();
  });

  it("signs out and forgets everything when unlinked", async () => {
    await savePairing(PAIRING, "AABB");
    await saveOpenOn("stock");
    await phone.load();
    signedIn(BOB);
    render(PairPage);

    await userEvent.click(screen.getByRole("button", { name: "Unlink this phone" }));
    const confirm = screen.getByRole("group", { name: "Confirm" });
    expect(confirm).toHaveAccessibleDescription(/signs this phone out/);
    await userEvent.click(within(confirm).getByRole("button", { name: "Unlink this phone" }));

    expect(await screen.findByRole("status")).toHaveTextContent("its token was revoked");
    expect(session.user).toBeNull();
    expect(server.calls.some((c) => c.url.endsWith("/auth/logout"))).toBe(true);
    expect(phone.openOn).toBeNull();
    expect(await native.secureGet("open_on")).toBeNull();
    expect(await native.secureGet("records")).toBeNull();
  });
});
