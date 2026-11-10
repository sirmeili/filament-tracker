// The layout picks the phone layout at 600px wide or less, and the header above that.
import { cleanup, render, screen } from "@testing-library/svelte";
import { createRawSnippet } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Me } from "#lib/api/types.ts";
import { viewport } from "#lib/viewport.svelte.ts";

const nav = vi.hoisted(() => ({
  page: { url: new URL("https://localhost/spools") },
  goto: vi.fn(),
}));
vi.mock("$app/state", () => ({ page: nav.page }));
vi.mock("$app/navigation", () => ({ goto: nav.goto }));
vi.mock("#lib/review-badge.svelte.ts", () => ({
  reviewBadge: { count: 3, refresh: vi.fn() },
}));

const { session } = await import("#lib/auth/session.svelte.ts");
const Layout = (await import("./+layout.svelte")).default;

const children = createRawSnippet(() => ({
  render: () => '<div class="pagehead"><h1>Spools</h1></div>',
}));

beforeEach(() => {
  session.user = { id: 1, username: "frank", role: "admin", time_zone: "UTC" } as Me;
  session.loaded = true;
});

afterEach(() => {
  cleanup();
  viewport().phone = false;
  session.user = null;
  session.loaded = false;
});

describe("the layout's shell", () => {
  it("shows the header with its nav on a wide screen", () => {
    viewport().phone = false;
    render(Layout, { children });

    expect(screen.getByRole("navigation", { name: "Main" })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "App" })).toBeNull();
    expect(screen.getByRole("main")).not.toHaveClass("phone");
  });

  it("shows the top bar and the bottom bar on a phone-sized screen", () => {
    viewport().phone = true;
    render(Layout, { children });

    expect(screen.queryByRole("navigation", { name: "Main" })).toBeNull();
    expect(screen.getByRole("link", { name: "RollCall, Inventory" })).toBeInTheDocument();
    const bar = screen.getByRole("navigation", { name: "App" });
    expect(bar).toBeInTheDocument();
    expect(screen.getByRole("main")).toHaveClass("phone");
    // The page's own heading stays for screen readers.
    expect(screen.getByRole("heading", { name: "Spools" })).toBeInTheDocument();
    // No Scan in a plain browser.
    expect(screen.queryByRole("link", { name: "Scan" })).toBeNull();
  });
});
