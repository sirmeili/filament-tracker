import { render, screen, waitFor } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { createRawSnippet } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Me } from "#lib/api/types.ts";

// The page URL and navigation, controlled by each test.
const nav = vi.hoisted(() => ({
  page: { url: new URL("https://tracker.example/") },
  goto: vi.fn(),
}));
vi.mock("$app/state", () => ({ page: nav.page }));
vi.mock("$app/navigation", () => ({ goto: nav.goto }));

const { session } = await import("#lib/auth/session.svelte.ts");
const Layout = (await import("./+layout.svelte")).default;
const LoginPage = (await import("./login/+page.svelte")).default;
const AccountPage = (await import("./account/+page.svelte")).default;
const HomePage = (await import("./+page.svelte")).default;

const children = createRawSnippet(() => ({ render: () => "<p>page content</p>" }));

function at(path: string): void {
  nav.page.url = new URL(path, "https://tracker.example");
}

function signedIn(user: Me | null): void {
  session.user = user;
  session.loaded = true;
  session.expired = false;
}

describe("layout", () => {
  beforeEach(() => {
    nav.goto.mockReset();
    signedIn(null);
  });
  afterEach(() => vi.restoreAllMocks());

  it("checks the session on first load", async () => {
    session.loaded = false;
    const load = vi.spyOn(session, "load").mockImplementation(async () => {
      session.loaded = true;
    });
    at("/spools");

    render(Layout, { children });

    expect(screen.getByText("Loading…")).toBeInTheDocument();
    await waitFor(() => expect(load).toHaveBeenCalledOnce());
  });

  it("offers a retry when the server cannot be reached", async () => {
    session.loaded = false;
    const load = vi.spyOn(session, "load").mockRejectedValue(new Error("down"));
    at("/");

    render(Layout, { children });

    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server.");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(load).toHaveBeenCalledTimes(2);
  });

  it("sends signed-out visitors to sign in", async () => {
    at("/review");

    render(Layout, { children });

    await waitFor(() =>
      expect(nav.goto).toHaveBeenCalledWith("/login?next=%2Freview", { replaceState: true }),
    );
    expect(screen.queryByText("page content")).toBeNull();
  });

  it("shows the sign-in page without navigation", () => {
    at("/login");

    render(Layout, { children });

    expect(screen.getByText("page content")).toBeInTheDocument();
    expect(screen.queryByRole("navigation")).toBeNull();
    expect(nav.goto).not.toHaveBeenCalled();
  });

  it("shows the page and the role's navigation when signed in", () => {
    signedIn({ id: 1, username: "alice", role: "editor" });
    at("/spools");

    render(Layout, { children });

    expect(screen.getByText("page content")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "alice" })).toHaveAttribute("href", "/account");
    expect(screen.getByRole("link", { name: "Spools" })).toHaveAttribute("aria-current", "page");
    expect(screen.queryByRole("link", { name: "Users" })).toBeNull();
  });

  it("shows how many items wait in Review", async () => {
    signedIn({ id: 1, username: "alice", role: "viewer" });
    const review = { flagged_events: [{}], unidentified_tags: [{}, {}], likely_empty: [] };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(review), { status: 200 })),
    );
    at("/");

    render(Layout, { children });

    expect(await screen.findByRole("link", { name: "Review, 3 waiting" })).toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it("refuses pages the role cannot open", () => {
    signedIn({ id: 1, username: "alice", role: "viewer" });
    at("/users");

    render(Layout, { children });

    expect(screen.getByRole("heading", { name: "No access" })).toBeInTheDocument();
    expect(screen.queryByText("page content")).toBeNull();
  });

  it("lets admins open admin pages", () => {
    signedIn({ id: 1, username: "root", role: "admin" });
    at("/users");

    render(Layout, { children });

    expect(screen.getByText("page content")).toBeInTheDocument();
  });
});

describe("pages", () => {
  beforeEach(() => {
    nav.goto.mockReset();
    signedIn(null);
  });
  afterEach(() => vi.restoreAllMocks());

  it("the sign-in page says when a session ended", () => {
    at("/login?expired=1");

    render(LoginPage);

    expect(screen.getByRole("status")).toHaveTextContent("Your session ended");
  });

  it("the account page shows the user and signs out", async () => {
    signedIn({ id: 1, username: "alice", role: "admin" });
    const logout = vi.spyOn(session, "logout").mockResolvedValue();
    at("/account");

    render(AccountPage);

    expect(screen.getByText("alice")).toBeInTheDocument();
    expect(screen.getByText("Admin")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(logout).toHaveBeenCalledOnce();
    expect(nav.goto).toHaveBeenCalledWith("/login", { replaceState: true });
  });

  it("the account page shows nothing about the user while signed out", () => {
    render(AccountPage);

    expect(screen.queryByText("Username")).toBeNull();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });

  it("every page renders in the browser only", async () => {
    const layout = await import("./+layout.ts");

    expect(layout.ssr).toBe(false);
    expect(layout.prerender).toBe(false);
    await expect(layout.load()).resolves.toBeUndefined(); // not the app: no native bridge
  });
});
