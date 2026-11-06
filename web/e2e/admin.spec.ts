// Review, manual entry, Devices, Users and Account against the real server. The seed
// (e2e/seed.py) flags a second Received on Black PLA spool 1 for Review.

import { expect, test } from "@playwright/test";
import { failOnBrowserErrors, signIn, signInAt } from "./helpers.ts";

failOnBrowserErrors();

test("editors accept a flagged event, then bring it back", async ({ page }) => {
  await signInAt(page, "/review", "e2e-editor");
  await expect(page.getByRole("heading", { name: "Received, flagged" })).toBeVisible();

  await page.getByRole("button", { name: "Accept Received on Black PLA Basic #1" }).click();
  await expect(page.getByRole("status")).toHaveText(/Accepted “Received” on Black PLA Basic #1/);
  await expect(page.getByText("Nothing flagged.")).toBeVisible();

  await page.getByRole("button", { name: "Bring back" }).click();
  await expect(page.getByRole("status")).toHaveText(/Brought back to Review/);
  await expect(page.getByRole("heading", { name: "Received, flagged" })).toBeVisible();
});

test("editors add a spool by hand with a new product", async ({ page }) => {
  await signInAt(page, "/spools", "e2e-editor");
  await page.getByRole("link", { name: "Add spool by hand" }).click();

  await page.getByLabel("A new product").check();
  await page.getByLabel("Name").fill("TPU 95A HF Black");
  await page.getByLabel("Filament type").fill("TPU");
  await page.getByLabel(/^Location/).fill("Foil bag drawer");
  await page.getByRole("button", { name: "Add spool" }).click();

  await expect(page).toHaveURL(/\/spools\/\d+$/);
  await expect(page.getByRole("heading", { name: "TPU 95A HF Black" })).toBeVisible();
  await expect(page.getByText("No tag yet")).toBeVisible();
});

test("admins register a scanner and see its token once", async ({ page }) => {
  await signInAt(page, "/devices", "e2e-admin");
  await page.getByRole("button", { name: "Register scanner" }).click();
  await page.getByLabel("Name").fill("Office scanner");
  await expect(page.getByLabel("ID")).toHaveValue("office-scanner");
  await page.getByRole("button", { name: "Create token" }).click();

  const panel = page.getByRole("alert", { name: "New token for Office scanner" });
  await expect(panel.locator("code")).toHaveText(/\S{20,}/);
  await expect(page.getByRole("article", { name: "Office scanner" })).toContainText("Never seen");

  await panel.getByRole("button", { name: "Done" }).click();
  await expect(panel).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("article", { name: "Office scanner" })).toBeVisible();
  await expect(page.locator("code")).toHaveCount(0);
});

test("admins create a user who then changes their password", async ({ page, browser }) => {
  await signInAt(page, "/users", "e2e-admin");
  await page.getByRole("button", { name: "Create user" }).click();
  await page.getByLabel("Username").fill("e2e-new");
  await page.getByLabel("First password").fill("first password 1");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("Created e2e-new (Viewer).");

  await page.getByLabel("Role for e2e-new").selectOption("editor");
  await expect(page.getByRole("status")).toHaveText("e2e-new is now Editor.");

  const other = await browser.newPage();
  await other.goto("/login?next=%2Faccount");
  await signIn(other, "e2e-new", "first password 1");
  await expect(other.getByRole("heading", { name: "e2e-new" })).toBeVisible();
  await expect(other.getByText("Editor", { exact: true })).toBeVisible();

  await other.getByLabel("Current password").fill("first password 1");
  await other.getByLabel("New password", { exact: true }).fill("second password 2");
  await other.getByLabel("Confirm new password").fill("second password 2");
  await other.getByRole("button", { name: "Change password" }).click();
  await expect(other.getByRole("status")).toHaveText(/^Password changed\./);

  await other.getByRole("button", { name: "Sign out" }).click();
  await signIn(other, "e2e-new", "second password 2");
  await expect(other.getByRole("link", { name: "e2e-new" })).toBeVisible();
  await other.close();
});
