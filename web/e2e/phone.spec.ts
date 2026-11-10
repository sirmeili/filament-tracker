// The web app at phone size (docs/mockups/mobile-web/): the top bar, the bottom bar and the
// menu sheet, against the real server. Wider screens keep the header (the other specs).

import { expect, test } from "@playwright/test";
import { failOnBrowserErrors, signInAt } from "./helpers.ts";

failOnBrowserErrors();
test.use({ viewport: { width: 390, height: 844 } });

test("a phone gets the bottom bar and the menu sheet", async ({ page }) => {
  await signInAt(page, "/", "e2e-admin");

  await expect(page.getByRole("navigation", { name: "Main" })).toHaveCount(0);
  const bar = page.getByRole("navigation", { name: "App" });
  await expect(bar).toBeVisible();
  // No Scan button in a plain browser.
  await expect(bar.getByRole("link", { name: "Scan" })).toHaveCount(0);

  await bar.getByRole("button", { name: "Menu" }).click();
  const menu = page.getByRole("dialog", { name: "Menu" });
  await expect(menu.getByRole("link", { name: "Inventory" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  await expect(menu.getByRole("navigation", { name: "Admin pages" })).toBeVisible();
  await menu.getByRole("link", { name: "Spools" }).click();

  await expect(page).toHaveURL(/\/spools$/);
  await expect(menu).toHaveCount(0);
  await expect(page.locator("header .title")).toHaveText("Spools");

  await bar.getByRole("link", { name: "e2e-admin" }).click();
  await expect(page).toHaveURL(/\/account$/);
  await expect(page.getByRole("group", { name: "Appearance" })).toBeVisible();
});

test("the menu closes on the dimmed page and with Escape", async ({ page }) => {
  await signInAt(page, "/", "e2e-viewer");
  const menuButton = page.getByRole("button", { name: "Menu" });

  await menuButton.click();
  await expect(page.getByRole("navigation", { name: "Admin pages" })).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);

  await menuButton.click();
  await page.mouse.click(195, 60);
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
