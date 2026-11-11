import type { CapacitorConfig } from "@capacitor/cli";

// The Android app (docs/SPEC.md, Phone scanner): the same SvelteKit build as the web app,
// with requests to the paired server made through Capacitor's native HTTP, so the server
// needs no CORS and keeps its session cookie and CSRF header rules.
const config: CapacitorConfig = {
  appId: "io.github.sirmeili.rollcall",
  appName: "RollCall",
  webDir: "build",
  android: {
    path: "../android",
  },
  // Capacitor logs every plugin call and its result in debug builds, which would put the
  // device token, the tag key constant and tag UIDs in the phone's log. Never log them.
  loggingBehavior: "none",
  plugins: {
    CapacitorHttp: { enabled: true },
    CapacitorCookies: { enabled: true },
  },
};

export default config;
