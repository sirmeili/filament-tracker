import { defineConfig, devices } from "@playwright/test";

const port = process.env.E2E_PORT ?? "8765";

export default defineConfig({
  testDir: "e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "node e2e/server.mjs",
    url: `http://127.0.0.1:${port}/api/v1/health`,
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
