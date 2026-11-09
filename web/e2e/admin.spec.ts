// Review, manual entry, Devices, Users and Account against the real server. The seed
// (e2e/seed.py) flags a second Received on Black PLA spool 1 for Review, and seeds a
// printer whose AMS reports White PLA spool 4 at 0%.

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

test("editors dismiss a used-up suggestion, then bring it back", async ({ page }) => {
  await signInAt(page, "/review", "e2e-editor");
  await expect(page.getByRole("heading", { name: "AMS reports 0% left" })).toBeVisible();

  await page.getByRole("button", { name: "Dismiss the suggestion for White PLA Basic #4" }).click();
  await expect(page.getByText(/^No suggestions\./)).toBeVisible();

  await page.getByRole("button", { name: "Bring back" }).click();
  await expect(page.getByRole("status")).toHaveText(/Brought back to Review/);
  await expect(page.getByRole("heading", { name: "AMS reports 0% left" })).toBeVisible();
});

test("admins see the printer and what is in its AMS", async ({ page }) => {
  await signInAt(page, "/devices", "e2e-admin");
  const printer = page.getByRole("article", { name: "E2E P1S" });

  await expect(printer).toContainText("Not connecting");
  await expect(printer).toContainText("No access code saved");
  await expect(printer).toContainText("192.0.2.10:8883");
  await expect(printer.getByRole("listitem", { name: "AMS 1, slot 1" })).toContainText(
    "Black PLA Basic #2",
  );
  await expect(printer.getByRole("listitem", { name: "AMS 1, slot 3" })).toContainText(
    "No Bambu tag, not tracked",
  );
  await expect(printer.getByRole("listitem", { name: "AMS 1, slot 4" })).toContainText("Empty");

  await printer.getByRole("link", { name: /White PLA Basic #4/ }).click();
  await expect(page.getByText("Loaded in AMS 1, slot 2 on E2E P1S")).toBeVisible();
});

test("admins add a printer, test it, rename it and remove it", async ({ page }) => {
  await signInAt(page, "/devices", "e2e-admin");
  await page.getByRole("button", { name: "Add printer" }).click();
  const form = page.getByRole("form", { name: "Add a printer" });
  await form.getByLabel("Name").fill("E2E Garage");
  // Port 1 on this machine refuses at once, so the server's link fails fast.
  await form.getByLabel("Address").fill("127.0.0.1");
  await form.getByLabel("Port").fill("1");
  await form.getByLabel("Serial").fill("E2E0002");
  await form.getByLabel("Access code").fill("e2e-code");
  await form.getByRole("button", { name: "Add printer" }).click();
  await expect(page.getByRole("status")).toHaveText(/Added E2E Garage\./);

  const card = page.getByRole("article", { name: "E2E Garage" });
  await expect(card).toContainText("127.0.0.1:1");
  await expect(card).not.toContainText("e2e-code");
  await card.getByRole("button", { name: "Edit" }).click();
  const edit = card.getByRole("form", { name: "Edit E2E Garage" });
  await edit.getByRole("button", { name: "Test" }).click();
  await expect(edit.getByRole("status")).toHaveText(/Can't reach the printer/);
  await edit.getByLabel("Name").fill("E2E Shed");
  await edit.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("status")).toHaveText(/Saved E2E Shed\./);

  const renamed = page.getByRole("article", { name: "E2E Shed" });
  await renamed.getByRole("button", { name: "Remove" }).click();
  await renamed.getByRole("button", { name: "Remove" }).click();
  await expect(page.getByRole("status")).toHaveText("Removed E2E Shed.");
  await expect(page.getByRole("article", { name: "E2E Shed" })).toHaveCount(0);
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

test("admins register a scanner and see its token and pairing code once", async ({ page }) => {
  await signInAt(page, "/devices", "e2e-admin");
  await page.getByRole("button", { name: "Register scanner" }).click();
  await page.getByLabel("Name").fill("Office scanner");
  await expect(page.getByLabel("ID")).toHaveValue("office-scanner");
  await page.getByRole("button", { name: "Create token" }).click();

  const panel = page.getByRole("alert", { name: "New token for Office scanner" });
  await expect(panel.locator("code")).toHaveText(/\S{20,}/);
  await expect(page.getByRole("article", { name: "Office scanner" })).toContainText("Never seen");

  const address = panel.getByLabel("Server address for the phone");
  await expect(address).toHaveValue(/^http:\/\/127\.0\.0\.1:/);
  // The phone cannot reach the admin's loopback address, so it must be changed first.
  await panel.getByRole("button", { name: "Show QR code" }).click();
  await expect(panel.getByRole("status")).toContainText("can't reach localhost");
  await address.fill("http://192.168.1.20:8000");
  await panel.getByRole("button", { name: "Show QR code" }).click();
  await expect(
    panel.getByRole("img", { name: "Pairing QR code for Office scanner" }),
  ).toBeVisible();

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

test("admins save a Home Assistant setting, test it and go back to the default", async ({
  page,
}) => {
  await signInAt(page, "/settings", "e2e-admin");
  const prefix = page.getByLabel("Discovery prefix", { exact: true });
  await expect(prefix).toHaveValue("homeassistant");

  await prefix.fill("e2e-ha");
  const ha = page.getByRole("form", { name: "Home Assistant" });
  await ha.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("status")).toHaveText(/Saved\./);
  await expect(page.getByText("Saved here", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Test" }).click();
  const results = page.getByRole("list", { name: "Test results" });
  await expect(results).toContainText("No broker set");
  await expect(results).toContainText("No address and token set");

  await page.getByRole("button", { name: "Use the .env value for Discovery prefix" }).click();
  await expect(prefix).toHaveValue("homeassistant");
  await expect(page.getByText("Saved here", { exact: true })).toHaveCount(0);
});

test("admins set the time zone, and the web app uses it", async ({ page }) => {
  await signInAt(page, "/settings", "e2e-admin");
  const zone = page.getByLabel("Time zone", { exact: true });
  await expect(zone).toHaveValue("UTC");

  const general = page.getByRole("form", { name: "General" });
  await zone.fill("America/Chicago");
  await general.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("status")).toHaveText("Saved.");
  const me = await page.evaluate(() => fetch("/api/v1/auth/me").then((r) => r.json()));
  expect(me.time_zone).toBe("America/Chicago");

  await page.getByRole("button", { name: "Use the .env value for Time zone" }).click();
  await expect(zone).toHaveValue("UTC");
});

test("the Settings page is for admins only", async ({ page }) => {
  await signInAt(page, "/settings", "e2e-editor");
  await expect(page.getByRole("heading", { name: "Settings" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Settings" })).toHaveCount(0);
});
