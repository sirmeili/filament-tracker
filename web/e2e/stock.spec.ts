// The stock pages against the real server and the seeded stock in e2e/seed.py:
// Black PLA (spool 1 sealed, spool 2 open at 12%) and Dark Gray PETG (spool 3 sealed).

import { expect, test } from "@playwright/test";
import { failOnBrowserErrors, signInAt } from "./helpers.ts";

failOnBrowserErrors();

test("viewers see inventory and spools without edit controls", async ({ page }) => {
  await signInAt(page, "/", "e2e-viewer");

  await expect(page.getByRole("heading", { name: "Black PLA Basic" })).toBeVisible();
  await expect(page.getByText("Open, nearly out").locator("..")).toContainText("1");
  await expect(page.getByText("LOW", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open spool, 12 percent left" })).toBeVisible();

  await page.getByRole("button", { name: "List" }).click();
  await expect(page.getByRole("table")).toContainText("Dark Gray PETG HF");

  await page
    .getByRole("navigation", { name: "Main" })
    .getByRole("link", { name: "Spools" })
    .click();
  // Other test files may add spools, so the total is not fixed.
  await expect(page.getByText(/^Showing 1–\d+ of \d+$/)).toBeVisible();
  await expect(page.getByRole("checkbox")).toHaveCount(0);

  await page.getByRole("link", { name: /Black PLA Basic #2/ }).click();
  await expect(page.getByText("12%", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /Mark|Undo|Save/ })).toHaveCount(0);
});

test("editors record an action on a spool and undo it", async ({ page }) => {
  await signInAt(page, "/spools/3", "e2e-editor");
  await expect(page.getByText("Sealed", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Mark opened" }).click();
  await expect(page.getByRole("status")).toHaveText("Recorded.");
  await expect(page.getByText("Open", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: /^Undo Opened/ }).click();
  await expect(page.getByText("Undid “Opened”.")).toBeVisible();
  await expect(page.getByText("Sealed", { exact: true })).toBeVisible();
});

test("editors move spools and edit notes", async ({ page }) => {
  await signInAt(page, "/spools", "e2e-editor");

  await page.getByRole("checkbox", { name: "Select spool 1" }).check();
  await page.getByRole("checkbox", { name: "Select spool 3" }).check();
  await page.getByLabel("Move to").fill("Dry box");
  await page.getByRole("button", { name: "Move", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("Moved 2 to Dry box.");
  await expect(page.getByRole("cell", { name: "Dry box" })).toHaveCount(2);

  await page.getByRole("link", { name: /Dark Gray PETG HF #3/ }).click();
  await page.getByLabel("Notes", { exact: true }).fill("Dried 8 h at 65 °C");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Saved")).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Notes", { exact: true })).toHaveValue("Dried 8 h at 65 °C");
});

test("editors change a product's settings", async ({ page }) => {
  await signInAt(page, "/products", "e2e-editor");

  await page.getByLabel("Nearly-out % for Dark Gray PETG HF").fill("20");
  await expect(page.getByText("1 product changed")).toBeVisible();
  await page.getByRole("button", { name: "Save changes" }).click();

  await expect(page.getByRole("status")).toHaveText("Saved");
  await page.reload();
  await expect(page.getByLabel("Nearly-out % for Dark Gray PETG HF")).toHaveValue("20");
});

test("the theme choice is remembered", async ({ page }) => {
  await signInAt(page, "/", "e2e-viewer");

  await page.getByRole("button", { name: "Dark theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

  await page.getByRole("button", { name: "Light theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});
