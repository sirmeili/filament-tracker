// Smoke test against the real server: sign-in, role-based navigation, sign-out, and the
// Content Security Policy that lets only the app's own scripts run.

import { expect, test } from "@playwright/test";
import { failOnBrowserErrors, signIn } from "./helpers.ts";

failOnBrowserErrors();

test("the app is served with a policy that allows only its own scripts", async ({ page }) => {
  const response = await page.goto("/");

  const policy = response?.headers()["content-security-policy"] ?? "";
  const scripts = policy.split(";").find((part) => part.trim().startsWith("script-src")) ?? "";
  // SvelteKit's start-up script and the theme script in app.html, by hash.
  expect(scripts.trim()).toMatch(/^script-src 'self'( 'sha256-[A-Za-z0-9+/=]+'){2}$/);
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});

test("signed-out visitors are sent to sign in, then back", async ({ page }) => {
  await page.goto("/spools");
  await expect(page).toHaveURL(/\/login\?next=%2Fspools$/);

  await signIn(page, "e2e-viewer");

  await expect(page).toHaveURL(/\/spools$/);
  await expect(page.getByRole("heading", { name: "Spools" })).toBeVisible();
});

test("a wrong password is refused with a clear message", async ({ page }) => {
  await page.goto("/login");

  await signIn(page, "e2e-viewer", "not the password");

  await expect(page.getByRole("alert")).toHaveText("Wrong username or password.");
  await expect(page).toHaveURL(/\/login$/);
});

test("viewers see no admin pages", async ({ page }) => {
  await page.goto("/login");
  await signIn(page, "e2e-viewer");
  await expect(page.getByRole("link", { name: "e2e-viewer" })).toBeVisible();

  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.getByRole("link", { name: "Inventory" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Users" })).toHaveCount(0);

  await page.goto("/users");
  await expect(page.getByRole("heading", { name: "No access" })).toBeVisible();
});

test("admins see every page", async ({ page }) => {
  await page.goto("/login");
  await signIn(page, "e2e-admin");

  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.getByRole("link", { name: "Users" })).toBeVisible();
  await nav.getByRole("link", { name: "Devices" }).click();
  await expect(page.getByRole("heading", { name: "Devices" })).toBeVisible();
});

test("signing out ends the session", async ({ page }) => {
  await page.goto("/login");
  await signIn(page, "e2e-editor");
  await page.getByRole("link", { name: "e2e-editor" }).click();

  await page.getByRole("button", { name: "Sign out" }).click();

  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/review");
  await expect(page).toHaveURL(/\/login\?next=%2Freview$/);
});
