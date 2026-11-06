import { installNativeBridge } from "#lib/phone/native-bridge.ts";

// A single-page app: pages render in the browser only, and the server answers every
// unknown path with index.html.
export const ssr = false;
export const prerender = false;

// In the Android app, connect to the native plugin before the first page renders.
export async function load(): Promise<void> {
  await installNativeBridge();
}
