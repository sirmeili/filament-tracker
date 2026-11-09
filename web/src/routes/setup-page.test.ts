import { render, screen, waitFor } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SetupStatus } from "#lib/api/setup.ts";
import { fakeFetch } from "../test/fixtures.ts";

const { session } = await import("#lib/auth/session.svelte.ts");
const SetupPage = (await import("./setup/+page.svelte")).default;

const ADMIN = { id: 1, username: "frank", role: "admin", time_zone: "America/Chicago" };
const OPEN: SetupStatus = { open: true, time_zone_needed: true, kdf_salt_needed: true };

function answer(status: number, detail: unknown): Response {
  return new Response(JSON.stringify({ detail }), { status });
}

function serve(reply: unknown) {
  const fetch = fakeFetch({ "POST /setup": reply });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

async function fill(code = "k7qm-x3rd-9pta"): Promise<void> {
  await userEvent.type(screen.getByLabelText("Setup code"), code);
  await userEvent.type(screen.getByLabelText("Username"), " Frank ");
  await userEvent.type(screen.getByLabelText("Password"), "correct horse battery");
}

function submit(): Promise<void> {
  return userEvent.click(screen.getByRole("button", { name: "Create Admin and sign in" }));
}

describe("Setup page", () => {
  beforeEach(() => {
    session.user = null;
    session.setup = { ...OPEN };
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    session.user = null;
    session.setup = null;
  });

  it("waits while setup is being checked", () => {
    session.setup = null;

    render(SetupPage);

    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("creates the first admin with the starter settings and signs them in", async () => {
    const fetch = serve(ADMIN);
    render(SetupPage);

    await fill();
    const zone = screen.getByLabelText("Time zone");
    await userEvent.clear(zone);
    await userEvent.type(zone, "America/Chicago");
    await userEvent.type(screen.getByLabelText("Key-derivation salt"), " 0a1b ");
    await submit();

    expect(fetch.calls[0]).toEqual({
      method: "POST",
      path: "/setup",
      body: {
        code: "k7qm-x3rd-9pta",
        username: "frank",
        password: "correct horse battery",
        time_zone: "America/Chicago",
        kdf_salt: "0a1b",
      },
    });
    await waitFor(() => expect(session.user?.username).toBe("frank"));
    expect(session.setup).toBeNull();
  });

  it("asks only for the starter settings the server needs", async () => {
    session.setup = { open: true, time_zone_needed: false, kdf_salt_needed: false };
    const fetch = serve(ADMIN);
    render(SetupPage);

    expect(screen.queryByLabelText("Time zone")).toBeNull();
    expect(screen.queryByLabelText("Key-derivation salt")).toBeNull();
    await fill();
    await submit();

    expect(fetch.calls[0].body).toEqual({
      code: "k7qm-x3rd-9pta",
      username: "frank",
      password: "correct horse battery",
    });
  });

  it("leaves out blank starter settings", async () => {
    const fetch = serve(ADMIN);
    render(SetupPage);

    await fill();
    await userEvent.clear(screen.getByLabelText("Time zone"));
    await submit();

    expect(fetch.calls[0].body).not.toHaveProperty("time_zone");
    expect(fetch.calls[0].body).not.toHaveProperty("kdf_salt");
  });

  it("checks the fields before sending", async () => {
    const fetch = serve(ADMIN);
    render(SetupPage);

    await userEvent.type(screen.getByLabelText("Password"), "short");
    await submit();

    expect(fetch.calls).toHaveLength(0);
    expect(screen.getByText("Enter the setup code from the server's log.")).toBeInTheDocument();
    expect(screen.getByText("Choose a username.")).toBeInTheDocument();
    expect(screen.getByText("The password needs at least 12 characters.")).toBeInTheDocument();
    expect(screen.getByLabelText("Setup code")).toHaveAttribute("aria-invalid", "true");
  });

  it("shows the server's problems by field", async () => {
    serve(
      answer(422, { problems: { time_zone: "not a time zone name", kdf_salt: "must be hex" } }),
    );
    render(SetupPage);

    await fill();
    await submit();

    expect(await screen.findByRole("alert")).toHaveTextContent("Check the fields marked below.");
    expect(screen.getByText("not a time zone name")).toBeInTheDocument();
    expect(screen.getByText("must be hex")).toBeInTheDocument();
    expect(screen.getByLabelText("Key-derivation salt")).toHaveAttribute("aria-invalid", "true");
  });

  it.each([
    [403, "That setup code is wrong."],
    [429, "Too many wrong codes."],
    [409, "Setup is already done."],
    [500, "boom"],
  ])("explains a %i", async (status, text) => {
    serve(answer(status, "boom"));
    render(SetupPage);

    await fill();
    await submit();

    expect(await screen.findByRole("alert")).toHaveTextContent(text);
    expect(session.user).toBeNull();
  });

  it("explains a failure that is not from the server", async () => {
    render(SetupPage);
    vi.spyOn(session, "finishSetup").mockRejectedValue(new Error("odd"));

    await fill();
    await submit();

    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong.");
  });
});
