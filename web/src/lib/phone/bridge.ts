/** What the phone app needs from Android, behind one interface.
 *
 * The Android app (Capacitor, with a Kotlin NFC plugin) installs the real bridge at
 * start-up with `setBridge`. In a browser the default bridge says it is not the app, so the
 * Scan and Pair screens are hidden and nothing native is called. Tests install fakes.
 */

/** Whether this phone can read Bambu tags right now. */
export type NfcStatus = "ready" | "no_nfc" | "nfc_off" | "no_mifare";

/** One tag read, as a scanner sends it: the UID and the 48 data blocks, without trailers. */
export interface TagRead {
  tagUid: string;
  blocks: string[];
  readOk: boolean;
}

export interface PhoneBridge {
  /** True only inside the Android app. */
  readonly app: boolean;
  readonly appVersion: string;
  nfcStatus(): Promise<NfcStatus>;
  /** Wait for the next tag and read it with keys derived from `saltHex`, which stays on the phone. */
  readTag(saltHex: string, signal: AbortSignal): Promise<TagRead>;
  /** Scan a QR code with the camera; null if the user backs out. */
  scanQr(): Promise<string | null>;
  /** Encrypted storage (the Android Keystore in the app). */
  secureGet(key: string): Promise<string | null>;
  secureSet(key: string, value: string): Promise<void>;
  secureRemove(key: string): Promise<void>;
}

function notInApp(): Promise<never> {
  return Promise.reject(new Error("Only available in the Android app"));
}

export const browserBridge: PhoneBridge = {
  app: false,
  appVersion: "web",
  nfcStatus: () => Promise.resolve("no_nfc"),
  readTag: notInApp,
  scanQr: notInApp,
  secureGet: notInApp,
  secureSet: notInApp,
  secureRemove: notInApp,
};

let current: PhoneBridge = browserBridge;

export function bridge(): PhoneBridge {
  return current;
}

export function setBridge(next: PhoneBridge): void {
  current = next;
}
