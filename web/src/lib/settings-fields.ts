/** What the Settings page shows for each setting, and what a Save sends. */

import type { CheckResult, SettingOut } from "#lib/api/settings.ts";

export interface FieldInfo {
  key: string;
  label: string;
  help: string;
  placeholder?: string;
  inputmode?: "numeric" | "text";
  /** Values offered as the admin types. */
  suggestions?: readonly string[];
}

/** IANA time zone names this browser knows, UTC first. */
export function timeZoneNames(
  supported: ((key: "timeZone") => string[]) | null = Intl.supportedValuesOf ?? null,
): string[] {
  const names = typeof supported === "function" ? supported("timeZone") : [];
  return ["UTC", ...names.filter((name) => name !== "UTC")];
}

export const GENERAL_FIELDS: readonly FieldInfo[] = [
  {
    key: "tz",
    label: "Time zone",
    help: "Every time in the web app is shown in it, whatever time zone a device uses.",
    placeholder: "America/New_York",
    suggestions: timeZoneNames(),
  },
  {
    key: "session_days",
    label: "Sign-in length (days)",
    help: "How long a sign-in lasts, from 1 to 365 days.",
    placeholder: "30",
    inputmode: "numeric",
  },
];

export const SCANNER_FIELDS: readonly FieldInfo[] = [
  {
    key: "bambu_kdf_salt",
    label: "Key-derivation salt",
    help: "The constant that turns a tag's UID into its keys, in hex. Empty: scanners and phones can't read tags.",
  },
  {
    key: "cf_access_client_id",
    label: "Cloudflare Access client ID",
    help: "A service token's Client ID, ending in .access. With the secret, paired phones pass Cloudflare Access when away from home. Empty: no token.",
    placeholder: "….access",
  },
  {
    key: "cf_access_client_secret",
    label: "Cloudflare Access client secret",
    help: "The same service token's Client Secret, shown once by Cloudflare.",
  },
];

export const HOME_ASSISTANT_FIELDS: readonly FieldInfo[] = [
  {
    key: "mqtt_url",
    label: "MQTT broker",
    help: "Home Assistant's broker, for the entities. mqtts:// for TLS. Empty: no entities.",
    placeholder: "mqtt://homeassistant.local:1883",
  },
  { key: "mqtt_user", label: "MQTT user", help: "The broker's user name." },
  { key: "mqtt_password", label: "MQTT password", help: "The broker user's password." },
  {
    key: "ha_discovery_prefix",
    label: "Discovery prefix",
    help: "Home Assistant's MQTT discovery prefix. Its default is homeassistant.",
    placeholder: "homeassistant",
  },
  {
    key: "ha_url",
    label: "Home Assistant address",
    help: "For firing events. Empty: no events.",
    placeholder: "http://homeassistant.local:8123",
  },
  {
    key: "ha_token",
    label: "Access token",
    help: "A long-lived access token, made on your Home Assistant profile page.",
  },
];

/** Where a value comes from, in words. */
export function sourceText(setting: SettingOut): string {
  if (setting.unreadable) return "Needs entering again";
  if (setting.source === "app") return setting.set ? "Saved here" : "Turned off here";
  if (setting.source === "env") return "From .env";
  return setting.set ? "Default" : "Not set";
}

/** The text box's starting value: a plain value, or empty for a secret. */
export function startValue(setting: SettingOut): string {
  return setting.secret ? "" : (setting.value ?? "");
}

/** Only what the admin changed: a plain value that differs from the one in use, or a
 * secret that was typed in. */
export function changedValues(
  settings: readonly SettingOut[],
  draft: Record<string, string>,
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const setting of settings) {
    const value = draft[setting.key] ?? "";
    if (setting.secret ? value.trim() !== "" : value.trim() !== (setting.value ?? "")) {
      out[setting.key] = value;
    }
  }
  return out;
}

const MQTT_RESULTS: Record<CheckResult, string> = {
  ok: "Connected to the broker.",
  off: "No broker set, so the entities are off.",
  unreachable: "Can't reach the broker. Check the address and port.",
  refused: "The broker refused the user name or password.",
  error: "The broker answered with an error.",
};

const EVENT_RESULTS: Record<CheckResult, string> = {
  ok: "Home Assistant accepted the token.",
  off: "No address and token set, so events are off.",
  unreachable: "Can't reach Home Assistant. Check the address.",
  refused: "Home Assistant refused the token.",
  error: "Home Assistant answered with an error.",
};

export function mqttResultText(result: CheckResult): string {
  return MQTT_RESULTS[result];
}

export function eventsResultText(result: CheckResult): string {
  return EVENT_RESULTS[result];
}
