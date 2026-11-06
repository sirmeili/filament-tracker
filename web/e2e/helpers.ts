// Shared by the end-to-end tests: sign-in, and a check that no page logged an error
// (a Content Security Policy violation or a script error shows up as one).

import { expect, test, type Page } from "@playwright/test";

export const PASSWORD = "e2e password 123";

export async function signIn(page: Page, username: string, password = PASSWORD): Promise<void> {
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

export async function signInAt(page: Page, path: string, username: string): Promise<void> {
  await page.goto(`/login?next=${encodeURIComponent(path)}`);
  await signIn(page, username);
  await expect(page).toHaveURL(new RegExp(`${path.replaceAll("/", "\\/")}$`));
}

// Expected failures: the signed-out check and a wrong password answer 401.
const EXPECTED = /Failed to load resource: the server responded with a status of 401/;

/** Fail each test in the file that logs a browser error. */
export function failOnBrowserErrors(): void {
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
    expect(errors.get(page)).toEqual([]);
  });
}
