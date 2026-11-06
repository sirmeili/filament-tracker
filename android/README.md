# Filament Tracker Android app

The phone scanner from `docs/SPEC.md` (Phone scanner): a Capacitor wrapper around the web app in `web/`, with a Kotlin plugin for NFC tag reading, QR scanning and Keystore storage. It works only on phones whose NFC chip reads MIFARE Classic, such as Google Pixel phones.

## Build

The build needs JDK 21 (newer JDKs fail with Gradle 8.14) and the Android SDK. Android Studio installs the SDK.

```sh
# From web/
npm run build
npx cap sync android

# From android/, with JAVA_HOME set to JDK 21
./gradlew coverageCheck    # Kotlin tests with the 90% coverage gate
./gradlew assembleDebug    # Writes app/build/outputs/apk/debug/app-debug.apk
```

Run `npm run build` and `npx cap sync android` again after any web change.

## Install on a phone

Either:

- **USB:** turn on Developer options and USB debugging on the phone, connect it, then run `adb install -r app/build/outputs/apk/debug/app-debug.apk`. `adb` is in the SDK's `platform-tools`.
- **File:** copy `app-debug.apk` to the phone and open it. Allow installs from that app when Android asks.

## Server for a phone test

The phone has to reach the server, so it must listen on the LAN, not only on `localhost`. From `server/`:

```sh
uv run uvicorn filament_tracker.main:create_app --factory --host 0.0.0.0 --port 8000
```

- Allow port 8000 through the PC's firewall for private networks.
- The pairing address is `http://<the PC's LAN address>:8000`. The app accepts plain `http://` only for LAN addresses.
- To sign in to the full web app over plain `http://`, also set `COOKIE_SECURE=false` in `server/.env`, for testing only. Scanning does not need it. Through the HTTPS reverse proxy, neither is needed.
- `BAMBU_KDF_SALT` must be set, or pairing stops with a message about it.

## Checklist

Run this before a release that changes the app, and record the results in `PROGRESS.md`.

**Setup and pairing**

1. First launch opens Pairing.
2. With NFC turned off in Android settings, Scan says NFC is off. With NFC turned on, it asks for a tap.
3. On the PC, register a device on Devices, set the server address and show the QR code. Scan it in the app: the app opens Scan, and within a minute Devices shows the phone Online with version `app-1.0`.
4. Typed pairing: an `http://` address that is not on the LAN, such as `http://example.com`, is refused with a message about the home network.

**Scanning**

5. Tap a spool the server knows: the card shows its name, color swatch and state with its date, and the suggested action is highlighted.
6. Choose an action: the app shows "Recorded …", and Activity shows the event from the phone.
7. Tap and choose nothing: after 15 seconds the screen goes back to waiting, and no event is recorded.
8. Choose the same action for the same spool twice within 30 seconds: Activity shows one event.
9. Undo on the last scan: the app shows "Undid …", and Activity shows the event undone.
10. Tap a spool the server has never seen: New is offered, and choosing it adds the spool.
11. Tap a card that is not a Bambu tag, such as a transit card: nothing breaks, and the app keeps waiting for a tap.
12. Pull a spool away during the read: the app keeps waiting for the next tap.
13. A sealed spool reads through its box, as in M0a.

**Offline**

14. Stop the server, then tap a spool: the card shows the product decoded on the phone with New, Opened and Empty. Choose one: Scan shows "1 queued".
15. Undo the queued scan: the queue is empty, and nothing reaches the server later.
16. Queue another scan, then start the server: within a few minutes the queue empties, and Activity shows the event with the time of the tap.
17. Close the app fully and reopen it: it opens on Scan, still paired, and a queued scan is still queued.

**Full web app and unpairing**

18. Open the full app and sign in: pages work, and "Back to Scan" returns to Scan.
19. Revoke the phone's token on Devices: the next scan says to pair the phone again.
20. Forget pairing in the app: it returns to Pairing.
21. With the phone on USB, `adb logcat` captured during pairing and a scan shows no device token, tag key constant, tag UID or block data. Search it for `ftd_` and for the UID's hex digits.

A phone without MIFARE Classic support should say so on Scan. A Pixel cannot show this, so it is covered by the web tests only.
