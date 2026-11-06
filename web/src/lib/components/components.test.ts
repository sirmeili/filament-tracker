import { render, screen } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "#lib/api/client.ts";
import { Session } from "#lib/auth/session.svelte.ts";
import Forbidden from "#lib/components/Forbidden.svelte";
import LoginForm from "#lib/components/LoginForm.svelte";
import Nav from "#lib/components/Nav.svelte";
import { NAV, visibleNav } from "#lib/nav.ts";

describe("Nav", () => {
  it("links each item and marks the current page", () => {
    render(Nav, { items: visibleNav("viewer"), current: NAV[1] });

    const links = screen.getAllByRole("link");
    expect(links.map((a) => a.textContent)).toContain("Spools");
    expect(screen.getByRole("link", { name: "Spools" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Inventory" })).not.toHaveAttribute("aria-current");
    expect(screen.queryByRole("link", { name: "Users" })).toBeNull();
  });
});

describe("Forbidden", () => {
  it("explains a page the role cannot open", () => {
    render(Forbidden);

    expect(screen.getByRole("heading", { name: "No access" })).toBeInTheDocument();
  });
});

describe("LoginForm", () => {
  afterEach(() => vi.restoreAllMocks());

  async function fillAndSubmit(): Promise<void> {
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Username"), "alice");
    await user.type(screen.getByLabelText("Password"), "secret password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
  }

  it("signs in with the username and password", async () => {
    const session = new Session();
    const login = vi.spyOn(session, "login").mockResolvedValue({
      id: 1,
      username: "alice",
      role: "viewer",
    });
    render(LoginForm, { session });

    await fillAndSubmit();

    expect(login).toHaveBeenCalledWith("alice", "secret password");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it.each([
    [new ApiError(401, "invalid username or password"), "Wrong username or password."],
    [new ApiError(429, "too many"), "Too many failed attempts. Try again in a few minutes."],
    [new ApiError(0, "Cannot reach the server"), "Cannot reach the server"],
    [new Error("odd"), "Something went wrong. Try again."],
  ])("shows a message when sign-in fails (%s)", async (failure, message) => {
    const session = new Session();
    vi.spyOn(session, "login").mockRejectedValue(failure);
    render(LoginForm, { session });

    await fillAndSubmit();

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(screen.getByLabelText("Password")).toHaveValue("");
    expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
  });

  it("says when the previous session ended", () => {
    render(LoginForm, { session: new Session(), expired: true });

    expect(screen.getByRole("status")).toHaveTextContent("Your session ended");
  });

  it("disables the button while signing in", async () => {
    const session = new Session();
    let finish: () => void = () => {};
    vi.spyOn(session, "login").mockReturnValue(
      new Promise((resolve) => {
        finish = () => resolve({ id: 1, username: "alice", role: "viewer" });
      }),
    );
    render(LoginForm, { session });

    await fillAndSubmit();

    expect(screen.getByRole("button", { name: "Signing in…" })).toBeDisabled();
    finish();
    expect(await screen.findByRole("button", { name: "Sign in" })).toBeEnabled();
  });
});
