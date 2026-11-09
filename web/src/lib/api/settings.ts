/** Calls behind the Settings page (Admin only). Secrets are write-only: the server only
 * says whether one is set. */

import { api, ApiError } from "#lib/api/client.ts";

export type SettingsGroup = "general" | "scanners" | "home-assistant";
export type SettingSource = "app" | "env" | "default";
export type CheckResult = "ok" | "off" | "unreachable" | "refused" | "error";

export interface SettingOut {
  key: string;
  /** Null for a secret, and for a setting that is not set. */
  value: string | null;
  secret: boolean;
  set: boolean;
  source: SettingSource;
  has_env: boolean;
  /** A saved secret the server's key cannot open: it needs entering again. */
  unreadable: boolean;
}

export interface GroupOut {
  group: SettingsGroup;
  settings: SettingOut[];
}

export interface TestOut {
  mqtt: CheckResult;
  events: CheckResult;
}

export function getSettings(group: SettingsGroup): Promise<GroupOut> {
  return api<GroupOut>(`/settings/${group}`);
}

/** Save values (an empty secret keeps the saved one) and clear secrets. */
export function saveSettings(
  group: SettingsGroup,
  values: Record<string, string>,
  clear: string[] = [],
): Promise<GroupOut> {
  return api<GroupOut>(`/settings/${group}`, { method: "PUT", body: { values, clear } });
}

/** Forget the value saved in the app, so the .env value (or the default) is used. */
export function useEnvValue(group: SettingsGroup, key: string): Promise<void> {
  return api<void>(`/settings/${group}/${encodeURIComponent(key)}`, { method: "DELETE" });
}

/** Try the entered values (on top of the saved ones) without saving them. */
export function testHomeAssistant(values: Record<string, string>): Promise<TestOut> {
  return api<TestOut>("/settings/home-assistant/test", { method: "POST", body: { values } });
}

/** The server's problems by setting, from a refused save. */
export function settingProblems(error: unknown): Record<string, string> | null {
  if (!(error instanceof ApiError) || error.status !== 422) return null;
  const detail = error.detail;
  if (detail && typeof detail === "object" && "problems" in detail) {
    const problems = (detail as { problems: unknown }).problems;
    if (problems && typeof problems === "object") return problems as Record<string, string>;
  }
  return null;
}
