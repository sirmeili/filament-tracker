// Start the real server for the end-to-end tests: a fresh database with one user per role,
// serving the built web app (run `npm run build` first). Playwright starts and stops it.

import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const web = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const server = resolve(web, "..", "server");
const data = join(web, "e2e", ".data");
const port = process.env.E2E_PORT ?? "8765";

rmSync(data, { recursive: true, force: true });
mkdirSync(data, { recursive: true });
const databaseUrl = `sqlite:///${join(data, "e2e.db").replaceAll("\\", "/")}`;

const seed = spawnSync("uv", ["run", "--project", server, "python", "e2e/seed.py", databaseUrl], {
  cwd: web,
  stdio: "inherit",
});
if (seed.status !== 0) process.exit(seed.status ?? 1);

const uvicorn = spawn(
  "uv",
  [
    "run",
    "--project",
    server,
    "uvicorn",
    "filament_tracker.main:create_app",
    "--factory",
    "--host",
    "127.0.0.1",
    "--port",
    port,
  ],
  {
    cwd: server,
    stdio: "inherit",
    env: {
      ...process.env,
      DATABASE_URL: databaseUrl,
      WEB_DIR: join(web, "build"),
      // The tests use plain HTTP on 127.0.0.1.
      COOKIE_SECURE: "false",
      ADMIN_TOKEN: "",
      // Never watch a real printer from a developer's server/.env; the seed has its own.
      PRINTERS: "[]",
      // Nor a real Home Assistant: the Settings tests start from nothing set.
      MQTT_URL: "",
      MQTT_USER: "",
      MQTT_PASSWORD: "",
      HA_URL: "",
      HA_TOKEN: "",
      SETTINGS_KEY: "",
    },
  },
);

for (const signal of /** @type {const} */ (["SIGINT", "SIGTERM"])) {
  process.on(signal, () => uvicorn.kill(signal));
}
uvicorn.on("exit", (/** @type {number | null} */ code) => process.exit(code ?? 0));
