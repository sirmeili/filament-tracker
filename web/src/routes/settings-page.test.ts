import { render, screen, waitFor, within } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SettingOut } from "#lib/api/settings.ts";
import type { MachineTokenOut } from "#lib/api/tokens.ts";
import { fakeFetch } from "../test/fixtures.ts";

const SettingsPage = (await import("./settings/+page.svelte")).default;

afterEach(() => vi.unstubAllGlobals());

function setting(key: string, fields: Partial<SettingOut> = {}): SettingOut {
  return {
    key,
    value: null,
    secret: false,
    set: false,
    source: "default",
    has_env: false,
    unreadable: false,
    ...fields,
  };
}

function group(overrides: Record<string, Partial<SettingOut>> = {}) {
  const base: SettingOut[] = [
    setting("mqtt_url", { value: "mqtt://broker:1883", set: true, source: "env", has_env: true }),
    setting("mqtt_user"),
    setting("mqtt_password", { secret: true }),
    setting("ha_discovery_prefix", { value: "homeassistant", set: true }),
    setting("ha_url"),
    setting("ha_token", { secret: true, set: true, source: "env", has_env: true }),
  ];
  return {
    group: "home-assistant",
    settings: base.map((s) => ({ ...s, ...(overrides[s.key] ?? {}) })),
  };
}

const GENERAL = {
  group: "general",
  settings: [
    setting("tz", { value: "UTC", set: true }),
    setting("session_days", { value: "30", set: true }),
  ],
};
const SCANNERS = { group: "scanners", settings: [setting("bambu_kdf_salt", { secret: true })] };

/** The form of one settings group. */
function form(name: string) {
  return within(screen.getByRole("form", { name }));
}

function serve(routes: Parameters<typeof fakeFetch>[0]) {
  const fetch = fakeFetch({
    "GET /settings/general": GENERAL,
    "GET /settings/scanners": SCANNERS,
    "GET /settings/home-assistant": group(),
    "GET /tokens": [],
    ...routes,
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

describe("Settings page", () => {
  it("shows each Home Assistant setting and where it comes from", async () => {
    serve({});
    render(SettingsPage);

    const url = await screen.findByLabelText("MQTT broker");
    expect(url).toHaveValue("mqtt://broker:1883");
    expect(screen.getAllByText("From .env")).toHaveLength(2);
    expect(form("Home Assistant").getByText("Default")).toBeInTheDocument();
    // A secret is never shown: its box is empty and says whether one is saved.
    const token = screen.getByLabelText("Access token");
    expect(token).toHaveValue("");
    expect(token).toHaveAttribute("type", "password");
    expect(token).toHaveAttribute("placeholder", "Saved. Leave empty to keep it.");
    expect(screen.getByLabelText("MQTT password")).toHaveAttribute("placeholder", "Not set");
    expect(form("Home Assistant").getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("saves only what changed and applies it", async () => {
    const fetch = serve({
      "PUT /settings/home-assistant": group({
        ha_url: { value: "http://ha:8123", set: true, source: "app" },
      }),
    });
    render(SettingsPage);

    await userEvent.type(await screen.findByLabelText("Home Assistant address"), "http://ha:8123");
    await userEvent.type(screen.getByLabelText("MQTT password"), "pw");
    await userEvent.click(form("Home Assistant").getByRole("button", { name: "Save" }));

    expect(fetch.calls.at(-1)).toEqual({
      method: "PUT",
      path: "/settings/home-assistant",
      body: { values: { ha_url: "http://ha:8123", mqtt_password: "pw" }, clear: [] },
    });
    expect(await screen.findByRole("status")).toHaveTextContent("Saved.");
    expect(screen.getByText("Saved here")).toBeInTheDocument();
    expect(screen.getByLabelText("MQTT password")).toHaveValue("");
  });

  it("shows refused values next to their setting", async () => {
    serve({
      "PUT /settings/home-assistant": () =>
        new Response(
          JSON.stringify({
            detail: { problems: { mqtt_url: "MQTT_URL must start with mqtt://" } },
          }),
          { status: 422 },
        ),
    });
    render(SettingsPage);

    const url = await screen.findByLabelText("MQTT broker");
    await userEvent.clear(url);
    await userEvent.type(url, "ftp://x");
    await userEvent.click(form("Home Assistant").getByRole("button", { name: "Save" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "MQTT broker: MQTT_URL must start with mqtt://",
    );
    expect(url).toHaveAttribute("aria-invalid", "true");
  });

  it("tests the entered values and explains the results", async () => {
    const fetch = serve({
      "POST /settings/home-assistant/test": { mqtt: "refused", events: "ok" },
    });
    render(SettingsPage);

    await userEvent.type(await screen.findByLabelText("MQTT user"), "ha");
    await userEvent.click(screen.getByRole("button", { name: "Test" }));

    const results = await screen.findByRole("list", { name: "Test results" });
    expect(within(results).getByText(/refused the user name or password/)).toBeInTheDocument();
    expect(within(results).getByText("Home Assistant accepted the token.")).toBeInTheDocument();
    expect(fetch.calls.at(-1)?.body).toEqual({ values: { mqtt_user: "ha" } });
  });

  it("clears a saved secret", async () => {
    const fetch = serve({
      "PUT /settings/home-assistant": group({ ha_token: { set: false, source: "app" } }),
    });
    render(SettingsPage);

    await userEvent.click(await screen.findByRole("button", { name: "Clear Access token" }));

    expect(fetch.calls.at(-1)?.body).toEqual({ values: {}, clear: ["ha_token"] });
    expect(await screen.findByText("Turned off here")).toBeInTheDocument();
  });

  it("goes back to the .env value", async () => {
    let saved = true;
    const fetch = serve({
      "GET /settings/home-assistant": () =>
        saved ? group({ mqtt_url: { value: "mqtt://other:1883", source: "app" } }) : group(),
      "DELETE /settings/home-assistant/mqtt_url": () => {
        saved = false;
        return null;
      },
    });
    render(SettingsPage);

    await userEvent.click(
      await screen.findByRole("button", { name: "Use the .env value for MQTT broker" }),
    );

    await waitFor(() =>
      expect(screen.getByLabelText("MQTT broker")).toHaveValue("mqtt://broker:1883"),
    );
    expect(fetch.calls.some((c) => c.method === "DELETE")).toBe(true);
    expect(screen.getByRole("status")).toHaveTextContent("Back to the .env value.");
  });

  it("offers the default when .env does not set it, and flags an unreadable secret", async () => {
    serve({
      "GET /settings/home-assistant": group({
        ha_discovery_prefix: { value: "ha2", source: "app" },
        mqtt_password: { source: "app", unreadable: true },
      }),
    });
    render(SettingsPage);

    expect(
      await screen.findByRole("button", { name: "Use the .env value for Discovery prefix" }),
    ).toHaveTextContent("Use the default");
    expect(screen.getByText("Needs entering again")).toBeInTheDocument();
  });

  it("says when the settings cannot be loaded or saved", async () => {
    const refused = () => new Response("{}", { status: 403 });
    vi.stubGlobal(
      "fetch",
      fakeFetch({
        "GET /settings/general": refused,
        "GET /settings/scanners": refused,
        "GET /settings/home-assistant": refused,
        "GET /tokens": refused,
      }),
    );
    render(SettingsPage);
    const alerts = await screen.findAllByRole("alert");
    // One for each settings group, and one for the machine tokens.
    expect(alerts).toHaveLength(4);
    expect(alerts[0]).toHaveTextContent("Your role cannot do that.");
  });

  it("reports a failed save that is not about one setting", async () => {
    serve({
      "PUT /settings/home-assistant": () =>
        new Response(JSON.stringify({ detail: "boom" }), { status: 500 }),
    });
    render(SettingsPage);

    await userEvent.type(await screen.findByLabelText("MQTT user"), "ha");
    await userEvent.click(form("Home Assistant").getByRole("button", { name: "Save" }));

    expect(await screen.findByRole("status")).toHaveTextContent("boom.");
  });

  it("shows the General and Scanners groups; only Home Assistant has Test", async () => {
    serve({});
    render(SettingsPage);

    expect(await screen.findByLabelText("Time zone")).toHaveValue("UTC");
    expect(screen.getByLabelText("Sign-in length (days)")).toHaveAttribute("inputmode", "numeric");
    const salt = screen.getByLabelText("Key-derivation salt");
    expect(salt).toHaveAttribute("type", "password");
    expect(salt).toHaveValue("");
    expect(screen.getAllByRole("button", { name: "Test" })).toHaveLength(1);
    // The time zone box suggests names.
    const list = document.getElementById(screen.getByLabelText("Time zone").getAttribute("list")!);
    expect(list?.querySelector('option[value="UTC"]')).not.toBeNull();
  });

  it("saving a time zone applies it to this browser at once", async () => {
    const { session } = await import("#lib/auth/session.svelte.ts");
    const { currentTimeZone, setTimeZone } = await import("#lib/format.ts");
    session.user = { id: 1, username: "frank", role: "admin", time_zone: "UTC" };
    const fetch = serve({
      "PUT /settings/general": {
        ...GENERAL,
        settings: [
          setting("tz", { value: "America/Chicago", set: true, source: "app" }),
          GENERAL.settings[1],
        ],
      },
    });
    render(SettingsPage);

    const zone = await screen.findByLabelText("Time zone");
    await userEvent.clear(zone);
    await userEvent.type(zone, "America/Chicago");
    await userEvent.click(form("General").getByRole("button", { name: "Save" }));

    expect(fetch.calls.at(-1)).toEqual({
      method: "PUT",
      path: "/settings/general",
      body: { values: { tz: "America/Chicago" }, clear: [] },
    });
    await waitFor(() => expect(session.user?.time_zone).toBe("America/Chicago"));
    expect(currentTimeZone()).toBe("America/Chicago");
    session.user = null;
    setTimeZone(undefined);
  });

  it("saves the salt without showing it", async () => {
    const fetch = serve({
      "PUT /settings/scanners": {
        group: "scanners",
        settings: [setting("bambu_kdf_salt", { secret: true, set: true, source: "app" })],
      },
    });
    render(SettingsPage);

    await userEvent.type(await screen.findByLabelText("Key-derivation salt"), "0a1b");
    await userEvent.click(form("Scanners").getByRole("button", { name: "Save" }));

    expect(fetch.calls.at(-1)?.body).toEqual({ values: { bambu_kdf_salt: "0a1b" }, clear: [] });
    expect(await screen.findByRole("status")).toHaveTextContent("next time they ask");
    expect(screen.getByLabelText("Key-derivation salt")).toHaveValue("");
    expect(screen.getByLabelText("Key-derivation salt")).toHaveAttribute(
      "placeholder",
      "Saved. Leave empty to keep it.",
    );
  });
});

const TOKEN: MachineTokenOut = {
  id: 1,
  name: "Home Assistant",
  role: "viewer",
  created_at: "2026-11-09T15:00:00Z",
  created_by: "frank",
  last_used_at: null,
  revoked: false,
};

/** The Machine tokens card. */
function tokensCard() {
  return within(screen.getByRole("region", { name: "Machine tokens" }));
}

describe("Machine tokens", () => {
  it("lists tokens with their role, maker and last use", async () => {
    serve({
      "GET /tokens": [
        { ...TOKEN, last_used_at: "2026-11-09T16:05:00Z" },
        { ...TOKEN, id: 2, name: "Old script", role: "admin", created_by: null, revoked: true },
      ],
    });
    render(SettingsPage);

    const list = await screen.findByRole("list", { name: "Machine tokens" });
    const rows = within(list).getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("Home Assistant");
    expect(rows[0]).toHaveTextContent("Viewer");
    expect(rows[0]).toHaveTextContent("by frank");
    expect(rows[0]).toHaveTextContent("Last used");
    expect(rows[1]).toHaveTextContent("Admin");
    expect(rows[1]).toHaveTextContent("Revoked");
    expect(rows[1]).toHaveTextContent("Never used");
    expect(rows[1]).not.toHaveTextContent("by ");
    expect(within(rows[1]).queryByRole("button")).toBeNull();
  });

  it("says when there are no tokens, and shows a load failure", async () => {
    serve({});
    const { unmount } = render(SettingsPage);
    expect(await tokensCard().findByText("No machine tokens yet.")).toBeInTheDocument();
    unmount();

    serve({ "GET /tokens": new Response(JSON.stringify({ detail: "nope" }), { status: 500 }) });
    render(SettingsPage);
    expect(await tokensCard().findByRole("alert")).toBeInTheDocument();
  });

  it("makes a token and shows it once", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText } });
    let made = false;
    const fetch = serve({
      "GET /tokens": () => (made ? [{ ...TOKEN, role: "editor" }] : []),
      "POST /tokens": () => {
        made = true;
        return { ...TOKEN, role: "editor", token: "ftm_secret-value" };
      },
    });
    render(SettingsPage);

    await userEvent.click(await tokensCard().findByRole("button", { name: "New token" }));
    const form = within(screen.getByRole("form", { name: "New machine token" }));
    await userEvent.click(form.getByRole("button", { name: "Make token" }));
    expect(form.getByRole("alert")).toHaveTextContent("Enter a name");

    await userEvent.type(form.getByLabelText("Name"), "  Home Assistant ");
    await userEvent.selectOptions(form.getByLabelText("Role"), "editor");
    await userEvent.click(form.getByRole("button", { name: "Make token" }));

    expect(fetch.calls.find((c) => c.method === "POST")?.body).toEqual({
      name: "Home Assistant",
      role: "editor",
    });
    const shown = await screen.findByRole("alert", { name: "New token for Home Assistant" });
    expect(shown).toHaveTextContent("ftm_secret-value");
    expect(shown).toHaveTextContent("It won't be shown again");
    await userEvent.click(within(shown).getByRole("button", { name: "Copy" }));
    expect(writeText).toHaveBeenCalledWith("ftm_secret-value");
    expect(shown).toHaveTextContent("Copied.");
    expect(await tokensCard().findByText("Editor")).toBeInTheDocument();

    await userEvent.click(within(shown).getByRole("button", { name: "Done" }));
    expect(screen.queryByText("ftm_secret-value")).toBeNull();
  });

  it("says when the token cannot be copied", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("denied"));
    vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText } });
    serve({ "POST /tokens": { ...TOKEN, token: "ftm_secret-value" } });
    render(SettingsPage);

    await userEvent.click(await tokensCard().findByRole("button", { name: "New token" }));
    await userEvent.type(screen.getByPlaceholderText("Home Assistant"), "HA");
    await userEvent.click(screen.getByRole("button", { name: "Make token" }));
    await userEvent.click(await screen.findByRole("button", { name: "Copy" }));

    expect(await screen.findByText(/Could not copy/)).toBeInTheDocument();
  });

  it("shows why a token was not made, and can be cancelled", async () => {
    serve({
      "POST /tokens": new Response(JSON.stringify({ detail: "requires the admin role" }), {
        status: 403,
      }),
    });
    render(SettingsPage);

    await userEvent.click(await tokensCard().findByRole("button", { name: "New token" }));
    await userEvent.type(screen.getByPlaceholderText("Home Assistant"), "HA");
    await userEvent.click(screen.getByRole("button", { name: "Make token" }));
    const form = within(screen.getByRole("form", { name: "New machine token" }));
    expect(await form.findByRole("alert")).toHaveTextContent("Your role cannot do that.");

    await userEvent.click(form.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("form", { name: "New machine token" })).toBeNull();
  });

  it("revokes a token after confirming", async () => {
    let revoked = false;
    const fetch = serve({
      "GET /tokens": () => [{ ...TOKEN, revoked }],
      "DELETE /tokens/1": () => {
        revoked = true;
        return new Response(null, { status: 204 });
      },
    });
    render(SettingsPage);

    await userEvent.click(await tokensCard().findByRole("button", { name: "Revoke" }));
    const confirm = within(tokensCard().getByRole("group", { name: "Confirm" }));
    await userEvent.click(confirm.getByRole("button", { name: "Cancel" }));
    expect(fetch.calls.some((c) => c.method === "DELETE")).toBe(false);

    await userEvent.click(tokensCard().getByRole("button", { name: "Revoke" }));
    await userEvent.click(tokensCard().getByRole("button", { name: "Revoke Home Assistant" }));

    expect(await tokensCard().findByRole("status")).toHaveTextContent("Revoked Home Assistant");
    expect(tokensCard().getByText("Revoked")).toBeInTheDocument();
    expect(tokensCard().queryByRole("button", { name: "Revoke" })).toBeNull();
  });

  it("shows why a revoke failed", async () => {
    serve({
      "GET /tokens": [TOKEN],
      "DELETE /tokens/1": new Response(JSON.stringify({ detail: "no such token" }), {
        status: 404,
      }),
    });
    render(SettingsPage);

    await userEvent.click(await tokensCard().findByRole("button", { name: "Revoke" }));
    await userEvent.click(tokensCard().getByRole("button", { name: "Revoke Home Assistant" }));

    expect(await tokensCard().findByRole("status")).toHaveTextContent("Not found");
  });
});
