/** Setting the phone up as the signed-in user's own phone (Pairing in docs/SPEC.md): after
 * signing in at home, the app asks the server for a device token of its own. */

import { api, ApiError } from "#lib/api/client.ts";
import type { PairingFields } from "#lib/pairing.ts";

const FALLBACK_NAME = "Android phone";
const MAX_NAME = 60;

/**
 * The phone's model, from the app's user agent ("Linux; Android 15; Pixel 9 Pro XL Build/…"),
 * to name it on the Devices page; "Android phone" when it cannot be told (Chrome's reduced
 * user agent says only "K").
 */
export function phoneName(userAgent: string = navigator.userAgent): string {
  const match = /Android [^;)]*;\s*([^;)]+?)(?:\s+Build\/[^;)]*)?\s*[;)]/.exec(userAgent);
  const model = [...(match?.[1] ?? "")]
    .filter((c) => c >= " " && c.charCodeAt(0) !== 127)
    .join("")
    .trim();
  if (!model || model === "K" || model === "wv") return FALLBACK_NAME;
  return model.slice(0, MAX_NAME);
}

interface OwnDevice {
  id: string;
  token: string;
}

/** Ask the server for this phone's own device token, as the signed-in user. */
export async function requestOwnPhone(
  url: string,
  name: string = phoneName(),
  fetchFn: typeof fetch = fetch,
): Promise<PairingFields> {
  const device = await api<OwnDevice>("/devices/mine", { method: "POST", body: { name } }, fetchFn);
  return { url, token: device.token, deviceId: device.id };
}

/** Why setting the phone up failed, in words; "away" when it must be done at home. */
export function setUpError(error: unknown): { away: boolean; text: string } {
  if (error instanceof ApiError) {
    if (error.status === 403) {
      return {
        away: true,
        text: "Finish setting up at home: your phone needs to be on your home network once.",
      };
    }
    if (error.status === 409) return { away: false, text: error.message };
    if (error.status === 0) {
      return { away: false, text: "Can't reach the server. Check your Wi-Fi and try again." };
    }
    if (error.status === 503) {
      return {
        away: false,
        text: "The server has no tag key constant yet. Set BAMBU_KDF_SALT on the server.",
      };
    }
  }
  return { away: false, text: "Setting up this phone failed. Try again." };
}
