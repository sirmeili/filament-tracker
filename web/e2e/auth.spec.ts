// Smoke test against the real server: sign-in, role-based navigation, sign-out, and the
// Content Security Policy that lets only the app's own scripts run.

import { expect, test, type Page } from "@playwright/test";

const PASSWORD = "e2e password 123";

async function signIn(page: Page, username: string, password = PASSWORD): Promise<void> {
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

// Expected failures: the signed-out check and a wrong password answer 401.
const EXPECTED = /Failed to load resource: the server responded with a status of 401/;
const errors = new WeakMap<Page, string[]>();

test.beforeEach(async ({ page }) => {
  const seen: string[] = [];
  errors.set(page, seen);
  page.on("console", (message) => {
    if (message.type() === "error" && !EXPECTED.test(message.text())) seen.push(message.text());
  });
  page.on("pageerror", (error) => seen.push(error.message));
});

test.afterEach(async ({ page }) => {
  // A CSP violation or a script error shows up here.
  expect(errors.get(page)).toEqual([]);
});

test("the app is served with a policy that allows only its own scripts", async ({ page }) => {
  const response = await page.goto("/");

  const policy = response?.headers()["content-security-policy"] ?? "";
  const scripts = policy.split(";").find((part) => part.trim().startsWith("script-src")) ?? "";
  expect(scripts.trim()).toMatch(/^script-src 'self' 'sha256-[A-Za-z0-9+/=]+'$/);
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
  await expect(page.getByText("e2e-viewer · Viewer")).toBeVisible();

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
  await page
    .getByRole("navigation", { name: "Main" })
    .getByRole("link", { name: "Account" })
    .click();

  await page.getByRole("button", { name: "Sign out" }).click();

  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/review");
  await expect(page).toHaveURL(/\/login\?next=%2Freview$/);
});
