import adapter from "@sveltejs/adapter-static";
import { sveltekit } from "@sveltejs/kit/vite";
import { svelteTesting } from "@testing-library/svelte/vite";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [
    sveltekit({
      // A single-page app: pages render in the browser, and the server answers unknown
      // paths with index.html (see server/src/filament_tracker/webapp.py).
      adapter: adapter({ fallback: "index.html", strict: true }),
      output: { bundleStrategy: "single" },
    }),
    svelteTesting(),
  ],
  server: {
    // `npm run dev` talks to a local server started with uvicorn on port 8000.
    proxy: { "/api": "http://localhost:8000" },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts", "scripts/**/*.test.ts"],
    setupFiles: ["src/test-setup.ts"],
    coverage: {
      provider: "v8",
      include: ["src/lib/**", "src/routes/**", "scripts/audit-policy.js"],
      exclude: ["**/*.test.ts"],
      thresholds: { lines: 90, functions: 90, branches: 90, statements: 90 },
    },
  },
});
