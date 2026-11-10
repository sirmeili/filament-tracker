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

test("a phone lists Inventory as compact rows that expand", async ({ page }) => {
  await signInAt(page, "/", "e2e-viewer");

  await expect(page.getByRole("group", { name: "View" })).toHaveCount(0);
  const row = page.getByRole("button", { name: /Black PLA Basic/ });
  await row.click();
  await expect(row).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByText("12%", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "View spools" }).click();
  await expect(page).toHaveURL(/\/spools\?q=Black\+PLA\+Basic$/);
  await expect(page.getByLabel("Search spools")).toHaveValue("Black PLA Basic");

  await page.goBack();
  await page.getByRole("button", { name: "Filter" }).click();
  const sheet = page.getByRole("dialog", { name: "Filter" });
  await sheet.getByRole("checkbox", { name: "Low stock only" }).check();
  await sheet.getByRole("button", { name: /^Show 1 product/ }).click();
  await expect(page.getByRole("button", { name: "Filter, 1 on" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Dark Gray PETG HF/ })).toHaveCount(0);
});

test("every page fits the phone's width, so the bottom bar stays on screen", async ({ page }) => {
  await signInAt(page, "/", "e2e-admin");
  const pages = ["/", "/spools", "/spools/1", "/products", "/review", "/activity"];
  for (const path of [...pages, "/devices", "/users", "/settings", "/account"]) {
    await page.goto(path);
    await expect(page.getByRole("navigation", { name: "App" })).toBeVisible();
    // Wait for the page's data before measuring.
    await expect(page.getByText("Loading…")).toHaveCount(0);
    const width = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(width, path).toBeLessThanOrEqual(390);
  }
});
