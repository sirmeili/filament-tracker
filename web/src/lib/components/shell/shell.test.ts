// The phone layout (docs/mockups/mobile-web/): the top bar, the bottom bar and the menu sheet.
import { cleanup, render, screen, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import type { Me } from "#lib/api/types.ts";
import PhoneNav from "#lib/components/shell/PhoneNav.svelte";
import PhoneTopBar from "#lib/components/shell/PhoneTopBar.svelte";
import { menuGroups, pageTitle } from "#lib/nav.ts";
import { PHONE_QUERY, Viewport } from "#lib/viewport.svelte.ts";

const ADMIN: Me = { id: 1, username: "frank", role: "admin", time_zone: "UTC" };
const VIEWER: Me = { id: 2, username: "bob", role: "viewer", time_zone: "UTC" };

afterEach(cleanup);

describe("page titles and menu groups", () => {
  it("names each page for the top bar", () => {
    expect(pageTitle("/")).toBe("Inventory");
    expect(pageTitle("/spools/7")).toBe("Spools");
    expect(pageTitle("/spools/new")).toBe("Add a spool");
    expect(pageTitle("/account")).toBe("Account");
    expect(pageTitle("/somewhere")).toBe("RollCall");
  });

  it("puts the Admin pages apart, and only for Admins", () => {
    const admin = menuGroups("admin");
    expect(admin.main.map((item) => item.label)).toEqual([
      "Inventory",
      "Spools",
      "Products",
      "Review",
      "Activity",
    ]);
    expect(admin.admin.map((item) => item.label)).toEqual(["Devices", "Users", "Settings"]);
    expect(menuGroups("viewer").admin).toEqual([]);
    expect(menuGroups(null)).toEqual({ main: [], admin: [] });
  });
});

describe("the phone-sized screen", () => {
  function media(matches: boolean) {
    const listeners: ((event: MediaQueryListEvent) => void)[] = [];
    const list = {
      matches,
      addEventListener: (_: string, listener: (event: MediaQueryListEvent) => void) =>
        listeners.push(listener),
    } as unknown as MediaQueryList;
    let asked = "";
    const matchMedia = (query: string) => {
      asked = query;
      return list;
    };
    return { matchMedia, listeners, asked: () => asked };
  }

  it("follows the window across 600px", () => {
    const fake = media(true);
    const screenSize = new Viewport(fake.matchMedia);
    expect(fake.asked()).toBe(PHONE_QUERY);
    expect(PHONE_QUERY).toBe("(max-width: 600px)");
    expect(screenSize.phone).toBe(true);

    fake.listeners[0]({ matches: false } as MediaQueryListEvent);
    expect(screenSize.phone).toBe(false);
  });

  it("is not a phone where the browser cannot tell", () => {
    expect(new Viewport(undefined).phone).toBe(false);
  });
});

describe("the top bar", () => {
  it("shows the mark, linking home, and the page title", () => {
    render(PhoneTopBar, { title: "Spools" });
    expect(screen.getByRole("link", { name: "RollCall, Inventory" })).toHaveAttribute("href", "/");
    expect(screen.getByText("Spools")).toBeInTheDocument();
  });
});

describe("the bottom bar", () => {
  it("has Menu and the user, with Scan only in the app", async () => {
    const bar = render(PhoneNav, { user: ADMIN, pathname: "/", reviewCount: 0 });
    const nav = screen.getByRole("navigation", { name: "App" });

    expect(within(nav).getByRole("button", { name: "Menu" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(within(nav).getByRole("link", { name: "frank" })).toHaveAttribute("href", "/account");
    expect(within(nav).queryByRole("link", { name: "Scan" })).toBeNull();

    await bar.rerender({ scan: true });
    expect(within(nav).getByRole("link", { name: "Scan" })).toHaveAttribute("href", "/scan");
  });

  it("marks the user on Account", () => {
    render(PhoneNav, { user: ADMIN, pathname: "/account", reviewCount: 0 });
    expect(screen.getByRole("link", { name: "frank" })).toHaveAttribute("aria-current", "page");
  });

  it("opens the menu with every page an Admin may open, the current one marked", async () => {
    render(PhoneNav, { user: ADMIN, pathname: "/spools/7", reviewCount: 4 });

    await userEvent.click(screen.getByRole("button", { name: "Menu" }));

    const menu = screen.getByRole("dialog", { name: "Menu" });
    const pages = within(menu).getByRole("navigation", { name: "Pages" });
    expect(within(pages).getAllByRole("link")).toHaveLength(5);
    expect(within(pages).getByRole("link", { name: "Review, 4 waiting" })).toHaveAttribute(
      "href",
      "/review",
    );
    const spools = within(pages).getByRole("link", { name: "Spools" });
    expect(spools).toHaveAttribute("aria-current", "page");
    expect(spools).toHaveFocus();
    const admin = within(menu).getByRole("navigation", { name: "Admin pages" });
    expect(
      within(admin)
        .getAllByRole("link")
        .map((link) => link.textContent),
    ).toEqual(["Devices", "Users", "Settings"]);
    expect(screen.getByRole("button", { name: "Close" })).toHaveAttribute("aria-expanded", "true");
  });

  it("hides the Admin pages from a Viewer", async () => {
    render(PhoneNav, { user: VIEWER, pathname: "/", reviewCount: 0 });
    await userEvent.click(screen.getByRole("button", { name: "Menu" }));

    expect(screen.queryByRole("navigation", { name: "Admin pages" })).toBeNull();
    expect(screen.queryByText("Admin")).toBeNull();
    expect(screen.getByRole("link", { name: "Inventory" })).toHaveFocus();
  });

  it("closes with Close, the dimmed page, Escape or a page link, focus back on Menu", async () => {
    render(PhoneNav, { user: ADMIN, pathname: "/", reviewCount: 0 });
    const open = () => userEvent.click(screen.getByRole("button", { name: "Menu" }));

    await open();
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByRole("button", { name: "Menu" })).toHaveFocus();

    await open();
    await userEvent.click(screen.getByRole("button", { name: "Close the menu" }));
    expect(screen.queryByRole("dialog")).toBeNull();

    await open();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByRole("button", { name: "Menu" })).toHaveFocus();

    await open();
    const products = screen.getByRole("link", { name: "Products" });
    products.addEventListener("click", (event) => event.preventDefault());
    await userEvent.click(products);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("keeps Tab among the menu's links", async () => {
    render(PhoneNav, { user: VIEWER, pathname: "/", reviewCount: 0 });
    await userEvent.click(screen.getByRole("button", { name: "Menu" }));
    const first = screen.getByRole("link", { name: "Inventory" });
    const last = screen.getByRole("link", { name: "Activity" });

    await userEvent.tab({ shift: true });
    expect(last).toHaveFocus();
    await userEvent.tab();
    expect(first).toHaveFocus();
    await userEvent.tab();
    expect(screen.getByRole("link", { name: "Spools" })).toHaveFocus();
    await userEvent.keyboard("a"); // other keys do nothing
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("closes when the page changes", async () => {
    const bar = render(PhoneNav, { user: ADMIN, pathname: "/", reviewCount: 0 });
    await userEvent.click(screen.getByRole("button", { name: "Menu" }));

    await bar.rerender({ pathname: "/spools" });

    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
