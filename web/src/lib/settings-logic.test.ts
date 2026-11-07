import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "#lib/api/client.ts";
import * as settings from "#lib/api/settings.ts";
import type { SettingOut } from "#lib/api/settings.ts";
import {
  changedValues,
  eventsResultText,
  mqttResultText,
  sourceText,
  startValue,
} from "#lib/settings-fields.ts";
import { fakeFetch } from "../test/fixtures.ts";

afterEach(() => vi.unstubAllGlobals());

function setting(fields: Partial<SettingOut> = {}): SettingOut {
  return {
    key: "ha_url",
    value: null,
    secret: false,
    set: false,
    source: "default",
    has_env: false,
    unreadable: false,
    ...fields,
  };
}

describe("settings API calls", () => {
  it("send the right method, path and body", async () => {
    const fetch = fakeFetch({
      "GET /settings/home-assistant": { group: "home-assistant", settings: [] },
      "PUT /settings/home-assistant": { group: "home-assistant", settings: [] },
      "DELETE /settings/home-assistant/ha_url": null,
      "POST /settings/home-assistant/test": { mqtt: "off", events: "off" },
    });
    vi.stubGlobal("fetch", fetch);

    await settings.getSettings("home-assistant");
    await settings.saveSettings("home-assistant", { ha_url: "http://ha" });
    await settings.saveSettings("home-assistant", {}, ["ha_token"]);
    await settings.useEnvValue("home-assistant", "ha_url");
    await settings.testHomeAssistant({ ha_url: "http://ha" });

    expect(fetch.calls.map((c) => [c.method, c.path, c.body])).toEqual([
      ["GET", "/settings/home-assistant", undefined],
      ["PUT", "/settings/home-assistant", { values: { ha_url: "http://ha" }, clear: [] }],
      ["PUT", "/settings/home-assistant", { values: {}, clear: ["ha_token"] }],
      ["DELETE", "/settings/home-assistant/ha_url", undefined],
      ["POST", "/settings/home-assistant/test", { values: { ha_url: "http://ha" } }],
    ]);
  });

  it("read the problems from a refused save", () => {
    const problems = { ha_url: "bad" };
    expect(settings.settingProblems(new ApiError(422, "x", { problems }))).toEqual(problems);
    expect(settings.settingProblems(new ApiError(422, "x", [{ msg: "x" }]))).toBeNull();
    expect(settings.settingProblems(new ApiError(422, "x", { problems: "no" }))).toBeNull();
    expect(settings.settingProblems(new ApiError(500, "x", { problems }))).toBeNull();
    expect(settings.settingProblems(new Error("x"))).toBeNull();
  });
});

describe("setting fields", () => {
  it("say where a value comes from", () => {
    expect(sourceText(setting({ source: "app", set: true }))).toBe("Saved here");
    expect(sourceText(setting({ source: "app" }))).toBe("Turned off here");
    expect(sourceText(setting({ source: "env", set: true }))).toBe("From .env");
    expect(sourceText(setting({ set: true }))).toBe("Default");
    expect(sourceText(setting())).toBe("Not set");
    expect(sourceText(setting({ source: "app", unreadable: true }))).toBe("Needs entering again");
  });

  it("never start a secret's box with a value", () => {
    expect(startValue(setting({ value: "http://ha" }))).toBe("http://ha");
    expect(startValue(setting())).toBe("");
    expect(startValue(setting({ secret: true, set: true }))).toBe("");
  });

  it("send only changed values", () => {
    const list = [
      setting({ key: "ha_url", value: "http://ha" }),
      setting({ key: "mqtt_user" }),
      setting({ key: "ha_token", secret: true, set: true }),
    ];
    expect(changedValues(list, { ha_url: "http://ha", mqtt_user: "", ha_token: "" })).toEqual({});
    expect(changedValues(list, { ha_url: " http://ha " })).toEqual({}); // only spaces differ
    expect(changedValues(list, { ha_url: "" })).toEqual({ ha_url: "" }); // turned off
    expect(changedValues(list, { ha_url: "http://other", ha_token: "t" })).toEqual({
      ha_url: "http://other",
      ha_token: "t",
    });
  });

  it("explain every test result", () => {
    for (const result of ["ok", "off", "unreachable", "refused", "error"] as const) {
      expect(mqttResultText(result)).toMatch(/\.$/);
      expect(eventsResultText(result)).toMatch(/\.$/);
    }
  });
});
