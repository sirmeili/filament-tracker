# RollCall Android app

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

Debug builds are **RollCall (dev)** (`io.github.sirmeili.rollcall.debug`, version `dev`). They install next to the release app instead of replacing it, each with its own pairing.

## Install a development build

- **USB:** turn on Developer options and USB debugging on the phone, connect it, then run `adb install -r app/build/outputs/apk/debug/app-debug.apk`. `adb` is in the SDK's `platform-tools`.
- **File:** copy `app-debug.apk` to the phone and open it. Allow installs from that app when Android asks.

## Installing on a phone (releases, with Obtainium)

Everyday phones run the release app, **RollCall** (`io.github.sirmeili.rollcall`), from this repository's GitHub Releases. [Obtainium](https://github.com/ImranR98/Obtainium) watches the releases and offers each new version.

1. Install Obtainium from its [GitHub releases](https://github.com/ImranR98/Obtainium/releases) (the `app-release.apk` for most phones) or from F-Droid. Allow installs from the browser (or F-Droid) when Android asks.
2. In Obtainium, tap **Add app** and enter `https://github.com/sirmeili/rollcall`. Before adding, set:
   - **Filter release titles by regular expression:** `^RollCall app ` (the repository may hold other releases later).
   - **Version string extraction RegEx:** `(\d+\.\d+\.\d+)`, so the tag `app-v1.2.0` reads as `1.2.0`, the version the app reports.
   - **Filter APKs by regular expression:** `^rollcall-.*\.apk$`.
3. Tap **Add**, then **Install**. Allow installs from Obtainium when Android asks.
4. Open RollCall **at home** and set it up by signing in (below). The server hands out the tag key and the Cloudflare Access token only on the home network.
5. Account shows the app's version (**RollCall app 1.2.0**); Devices shows each phone's version too.

Updates: Obtainium checks in the background and notifies when a release is out; tap **Update**. Android keeps the app's data, so the phone stays set up. An update must be signed with the same key as the installed app, so a phone with an app signed by another key (an old debug build) must uninstall it first.

## Releases

A release is published by pushing a tag `app-v<major>.<minor>.<patch>` (each part 0 to 99) on a commit in `main`. The **App release** workflow (`.github/workflows/app-release.yml`) then builds the web app and the Android app at that version (version code `major·10000 + minor·100 + patch`), runs the Kotlin tests, signs it with the release key, checks it with `scripts/verify-release.sh` (app ID, version, a v2 signature and, when set, the expected certificate) and attaches `rollcall-<version>.apk` to a GitHub Release named **RollCall app <version>**, with its SHA-256, the certificate's SHA-256 and the merged pull requests.

```sh
git switch main && git pull
git tag app-v1.2.0
git push origin app-v1.2.0
```

Make a release when a merged change affects the phone: the app holds its own copy of the web app, so a web change reaches the phones only in a new release. CI also builds a test release on every pull request, signed with a key made for that run, so a broken release setup shows up before a tag.

### The release key (once)

Every release must be signed with the same key: Android refuses an update signed by another, and the phones would have to uninstall and set up again. The owner keeps the key; it is never in the repository (`*.jks` is ignored).

1. Make it with JDK 21's `keytool`, in a folder outside the repository, choosing a long password when asked:

   ```sh
   keytool -genkeypair -keystore rollcall-release.jks -storetype PKCS12 -alias rollcall      -keyalg RSA -keysize 4096 -validity 36500 -dname "CN=RollCall"
   ```

2. Keep `rollcall-release.jks` and the password in a password manager (or two safe places). Losing them means every phone reinstalls.
3. Store them as repository secrets (PowerShell, from the key's folder):

   ```powershell
   [Convert]::ToBase64String([IO.File]::ReadAllBytes("rollcall-release.jks")) | gh secret set ANDROID_KEYSTORE_BASE64 -R sirmeili/rollcall
   gh secret set ANDROID_KEYSTORE_PASSWORD -R sirmeili/rollcall   # paste the password when asked
   ```

4. Record the certificate's SHA-256, so the workflow refuses a release signed with any other key:

   ```powershell
   keytool -list -keystore rollcall-release.jks -alias rollcall   # asks for the password
   gh variable set RELEASE_CERT_SHA256 -R sirmeili/rollcall --body "<the SHA-256 without colons>"
   ```

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

1. First launch opens "Set up this phone", asking for the server's address, with "Pair with a code instead".
2. With NFC turned off in Android settings, Scan says NFC is off. Turn NFC on and come back: within a few seconds it asks for a tap, without restarting the app.
3. Pair with a code instead: on the PC, register a device on Devices, set the server address and show the QR code. Scan it in the app: the app opens Scan, and within a minute Devices shows the phone Online with version `app-1.0`.
4. Typed pairing: an `http://` address that is not on the LAN, such as `http://example.com`, is refused with a message about the home network.

**Scanning**

5. Tap a spool the server knows: once the whole tag is read the phone buzzes once and beeps (the beep follows the notification volume); the card then shows its name, color swatch and state with its date, and the suggested action is highlighted.
6. Choose an action: the app shows "Recorded …", and Activity shows the event from the phone.
7. Tap and choose nothing: after 15 seconds the screen goes back to waiting, and no event is recorded.
8. A known spool never offers the same action twice, so this one is checked offline (see 14).
9. Undo on the last scan: the app shows "Undid …", and Activity shows the event undone.
10. Tap a spool the server has never seen: New is offered, and choosing it adds the spool.
11. Tap a card that is not a Bambu tag, such as a transit card: nothing breaks, and the app keeps waiting for a tap.
12. Pull a spool away during the read: two short buzzes and a low tone, and the app keeps waiting for the next tap. Leave a spool on the phone after a read: it is not read again until it is lifted and tapped again.
13. A sealed spool reads through its box, as in M0a.

**Offline**

14. Stop the server, then tap a spool: the card shows the product decoded on the phone with New, Opened and Empty. Choose one: Scan shows "1 queued". Tap the same spool within 30 seconds and choose the same action: the app says it was already recorded, and the queue still holds one scan (check 8).
15. Undo the queued scan: the queue is empty, and nothing reaches the server later.
16. Queue another scan, then start the server: within a few minutes the queue empties, and Activity shows the event with the time of the tap.
17. Close the app fully and reopen it: it opens on Scan, still paired, and a queued scan is still queued.

**Full web app and unpairing**

18. Open the full app and sign in: pages work, and "Back to Scan" returns to Scan.
19. Revoke the phone's token on Devices: the next scan says to pair the phone again.
20. Unlink this phone (from Scan's Pairing button): it returns to Pairing, says the token was revoked, and Devices lists the phone as revoked.
21. Pair again, stop the server, then open the full app: "Cannot reach the server" offers Phone pairing. Unlink there: the app says the server could not be reached and the phone is still listed; Devices still shows it active until revoked there.
22. Away from home (mobile data, with the Access service token saved in Settings and the app opened once at home): the pages load without an Access sign-in, Scan shows Away, and a scan is decoded on the phone and queued. Back home, the queue empties and Activity shows the scan.
23. Without the service token, away from home: Scan shows Offline (not Online), a queued scan stays queued, and sign-in says it cannot reach the server instead of waiting.
24. With the phone on USB, `adb logcat` captured during pairing and a scan shows no device token, tag key constant, tag UID or block data. Search it for `ftd_` and for the UID's hex digits.

**Setting up by signing in**

25. Unlink, then at home enter the server's address and sign in as an Editor: the app sets itself up without a code and asks what the phone is mainly for. Devices lists the phone under its model name, belonging to that user.
26. Choose "Looking at stock": the app opens on Inventory, now and after closing and reopening it. Change it to "Scanning" on the Pairing page: it opens on Scan.
27. Scan a spool and record an action: Activity shows it as "user (phone model)".
28. Set up a phone as a Viewer: tapping a spool shows its card with Info and Cancel only and "Your account can look spools up but not record them", online and with the server stopped.
29. Try setting up away from home (mobile data): the app says to finish setting up at home. "Use a different server" goes back to the address.
30. Unlink a phone set up by signing in: it is signed out and back at the address step.

A phone without MIFARE Classic support should say so on Scan. A Pixel cannot show this, so it is covered by the web tests only.
