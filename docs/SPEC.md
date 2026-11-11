# RollCall — Spec

*RollCall is a working name (2026-11-09, replacing Spoolhouse) and may change. The GitHub repo is `sirmeili/rollcall`, and the Docker image, container and volumes use `rollcall`. The project was called Filament Tracker. Every name people see (the web app, the phone app, the Home Assistant device, the docs) says RollCall (2026-11-10); the code's identifiers keep the old name until the rename; see Future enhancements: print requests, Name and rename.*

Oct 31, 2026 · @Frank

## Overview

A self-hosted system that tracks every Bambu Lab filament spool from delivery to empty, using the RFID tags already on the spools. You tap a spool on a small touchscreen scanner, or on an Android phone running the companion app; it shows what the spool is and asks whether it is new, just opened or empty. A central server keeps the inventory, feeds Home Assistant and serves a web app that a few people can use, some only to view.

Later phases turn it into a combined inventory and print request tool: a co-owner of the printer submits print requests, chooses from the filament in stock or the full Bambu catalog, and follows each print to pick-up. See Future enhancements: print requests; nothing in it changes the milestones up to M9.

**Goals**

- Know at a glance how many sealed and open spools exist for each filament (for example: Black PLA Basic, 3 sealed, 1 open).
- Record each spool's lifecycle with one tap and one confirm: New, Opened, Empty.
- Identify spools automatically from their Bambu RFID tags, with no manual typing of type or color.
- Use the P1S/AMS telemetry to fill in what the printer already knows (spool first loaded, remaining %).
- Surface low-stock alerts and inventory sensors in Home Assistant.
- Run in Docker with no Bambu cloud dependency. Scanners and integrations stay on the LAN; the web app can be reached from the internet through an HTTPS reverse proxy, with personal accounts.

**Non-goals (v1)**

- Writing or cloning Bambu tags. Tags are read-only; Bambu's RSA signature makes new tags impossible anyway.
- Weighing spools with a load cell (possible later add-on).
- Third-party filament without Bambu tags (see Open questions).
- Slicer integration or automatic filament usage from G-code. (Phase 3 of print requests reads slicer estimates from 3MF files, not G-code.)

## Background: Bambu RFID tags

Bambu spools carry MIFARE Classic 1K tags whose sector keys can be derived from the tag UID, so a cheap reader can decode the full contents. Reference: the [Bambu Research Group RFID Tag Guide](https://github.com/Bambu-Research-Group/RFID-Tag-Guide) (block map in BambuLabRfid.md, `deriveKeys.py`).

- **UID**: 4 bytes, unencrypted, unique per tag.
- **Keys**: 16 sector keys derived from the UID via HKDF-SHA256 with a published constant (the "salt"). Treat the constant as configuration, never hard-code it in the repo.
- **Two tags per spool**: one on each side of the spool, with different UIDs. Both carry the same per-spool tray UID, which is the spool's identity in this system.
- **Content**: filament material and variant IDs, filament type, color (RGBA), spool weight, diameter, print and drying temperatures, production date, and an RSA signature.
- **Same product, different bytes**: two rolls of Black PLA Basic share the material and color fields but differ in UID, tray UID, production date and signature.
- **Read-only**: the signature prevents creating valid new tags. This system only reads.

iPhones cannot read MIFARE Classic. The readers in this project are PN532-class or PC/SC devices, plus Android phones whose NFC chip supports MIFARE Classic (see Phone scanner).

## User workflows

Every workflow starts the same way: tap a spool (or its box) on the reader. The screen shows what the spool is and asks what to do, offering only the actions that make sense for its current state.

1. Tap a spool. The device sends a `lookup` to the server.
2. The screen shows the product name, a color swatch from the tag, the current state with its date ("Sealed, received Oct 12") and up to three action labels above the three buttons.
3. The suggested action is highlighted. Press its button or tap it on screen to confirm.
4. The device sends the action, shows the result for 3 seconds and returns to idle. No choice within 15 seconds cancels with no event sent.

**Actions offered after a scan**

| Spool state | Left key | Middle key | Right key |
| --- | --- | --- | --- |
| Unknown | New ★ | Opened | Empty |
| Sealed | Opened ★ | Empty | Cancel |
| Open | Empty ★ | Info | Cancel |
| Empty | Info ★ | — | Cancel |

★ marks the suggested action. New records a `received` event. Info shows the AMS remaining % and the spool's recent events.

**Soft keys and menu**

The three physical buttons sit directly under the screen. Each button's current meaning is drawn on screen above it, and the same labels are touch targets, so buttons and touch are interchangeable.

| Screen | Left | Middle | Right |
| --- | --- | --- | --- |
| Idle ("Tap a spool") | Menu | Last scan | Status |
| After a scan | Action 1 | Action 2 | Action 3 |
| Menu | Up | OK | Down |

A long press on the middle button means Back from any screen.

Menu items:

- **Re-ask last scan**: reopens the question for the last spool without rescanning it.
- **Adjust last scan**: change the action chosen, or undo it.
- **Recent scans**: the last 10 scans, each selectable to adjust.
- **Device status**: Wi-Fi, server connection, queued events.
- **Settings**: brightness, sound, timeout.

**Rules**

- Out-of-order actions are accepted and recorded, not refused. Example: Empty on a spool never marked Opened sets both `opened_at` and `emptied_at`, and the event is flagged for review.
- Choosing Opened or Empty on an unknown spool creates it first (an implicit Received).
- Either of the spool's two tags works; both resolve to the same spool.
- Offline: if the lookup fails, the screen offers New, Opened and Empty with the product decoded from the raw tag, and the chosen event is queued. The server applies the same rules when it arrives.
- Replay order: events are replayed by `occurred_at`, not by arrival, so a queued event takes its true place in the spool's history.
- A queued Opened that still falls after the spool's Empty is applied: the spool becomes `open` and the event is flagged for review.
- A `received` on a spool that is already `open` or `empty` is recorded and flagged for review, with no state change. A second roll of the same product is a different spool, because it has its own tray UID.

**Manual entry (tags that cannot be read yet)**

Some spools cannot be scanned when they arrive; TPU, for example, ships in a foil bag that blocks the tag.

- In the web UI (phone or computer), choose a product and record New. This creates a placeholder spool with no tray UID.
- If the product has never been scanned, enter its name, filament type and color by hand. It is created as a provisional product and merged into the real product when one of its tags is scanned. A scanned tag matches a provisional product when the filament type and color are the same and the product still has unlinked placeholders; if several match, none is used and the scan is treated as a new product.
- The first scan of an unknown tray UID whose product has unlinked placeholders shows the oldest placeholder, with its state and date, instead of an unknown spool. Confirming an action links the tag to that placeholder, so its history carries over, and the link event is flagged for review so a wrong match can be corrected.

**Automatic detection from the AMS**

- The first time the P1S/AMS reports a tray UID the server has not seen opened, the spool moves to `open` with source `ams`. This covers spools opened and loaded without a scan. It happens once per spool: if that `opened` is undone, the AMS does not record it again.
- A spool first seen through the AMS is assigned to an existing product if its AMS data matches exactly one: the same material ID (the AMS `tray_info_idx`) and color. If it matches none or several, the server creates a provisional product from the AMS filament type, color and material ID, marked as made from the AMS (shown as "From the AMS"). Either way the spool is flagged for review. A later scan of one of its tags settles the product (owner, 2026-11-10: a name given to a product the AMS made is kept): a product with the tag's key wins, and the spool moves to it (a provisional product left with no spools is removed). Otherwise the spool's own provisional product is filled in with the tag's IDs and keeps its name. A tag of another spool fills in the one provisional product made from the AMS with the tag's material ID and color, if there is exactly one.
- Trays with no tray UID (all zeros, for example a non-Bambu spool) are shown in their slot but create no spool. A remaining % of -1 means the AMS does not know it, and is ignored.
- The AMS remaining % is stored on the spool and shown in the UI. It is written only when it changes.
- The server remembers what is in each AMS slot, so the Devices page, the Spools table and Spool detail can show where a spool is loaded.
- When the AMS reports 0% remaining for an open spool, the server raises a "Likely empty" suggestion; it does not mark the spool empty on its own. The suggestion lasts until the spool is emptied, the AMS reports more than 0%, or it is dismissed.

## System architecture

&#91;embedded content: system architecture · 5 components around one server\]

Scanners post raw tag dumps to the API and the printer reports AMS trays over MQTT; the server decodes, logs every event in SQLite, publishes to Home Assistant and serves the web UI.

## Scanner device: hardware

One ESP32 touchscreen board, one PN532 reader and three soft-key buttons under the screen, in an enclosure printed on the P1S. v1 uses the ESP32 "Cheap Yellow Display" (CYD) to reach a working prototype fast; a custom PCB is listed under Future enhancements.

| Part | Choice | Notes |
| --- | --- | --- |
| MCU + display | ESP32-2432S028R "Cheap Yellow Display": ESP32, 2.8" 320×240 color TFT, resistive touch | About $15; CheapSpoolDisplay already pairs this board with a PN532 for Bambu tags |
| Reader | PN532 over I2C on the CYD's extension connector | Must support MIFARE Classic authentication; ESPHome's PN532 component does not read Classic sectors |
| Buttons | 3 momentary buttons under the screen, read through a resistor ladder on one ADC pin (GPIO35, input-only, external pull-up) | Free GPIO on the CYD is scarce. Fallback: a PCF8574 I2C expander on the PN532 bus |
| Sound | Small speaker on the CYD's speaker connector | Confirms a scan without looking |
| Status | Shown on screen | The CYD's onboard RGB LED faces the back, so it is not used |
| Power | USB-C 5 V |  |
| Enclosure | Printed case: screen and keys on the front, antenna under a flat "tap here" zone | Antenna face covered by 1 mm or less of plastic |

**Requirements**

- Reads a tag through a 1 mm printed lid and, if possible, through the shipping box (to be measured in milestone 0).
- Screen and key labels readable at arm's length; touch targets at least 48 px tall.
- Placement: wall-mounted by default, as the case is designed, or on a shelf, near where boxes are unpacked; a second unit can sit by the printer.
- Bill of materials target: under $30 per unit, excluding the printed case. The parts list is in `hardware/BOM.md`.

## Scanner firmware

The firmware stays dumb: it reads the UID, derives the keys, dumps the raw blocks and posts them with the chosen action. The server owns the authoritative decode, where it is easier to test and fix; the device decodes only product, type and color for the screen and offline use.

**Stack**: PlatformIO with the Arduino framework (C++), a PN532 library that supports MIFARE Classic authentication, and HKDF-SHA256 from mbedTLS (built into ESP-IDF), and LVGL on TFT\_eSPI for the screen, touch and menus.

**Behavior**

1. Idle: screen shows "Tap a spool" and the idle soft keys (Menu, Last scan, Status); reader polling.
2. Tag detected: read UID, derive the 16 keys, authenticate and read every data block.
3. Send a `lookup` scan event; the server returns spool, product, state, allowed actions and the suggested action.
4. Draw the spool card (name, color swatch, state) and the action labels; wait up to 15 seconds for a key press or touch.
5. Send the chosen action as a second scan event with the same raw blocks.
6. Show the server's answer (success, already in that state, flagged, error) with a sound, then return to idle.
7. Buttons are read by ADC thresholds with debounce; a long press (over 1 second) on the middle key is Back.

**Scan event payload** (JSON over HTTPS or HTTP on the LAN)

| Field | Type | Notes |
| --- | --- | --- |
| `event_id` | UUID | Generated on the device; makes retries idempotent |
| `device_id` | string | Set at provisioning |
| `action` | enum | `received`, `opened`, `empty`, `lookup` |
| `tag_uid` | hex string | 4-byte UID |
| `blocks` | hex string array | Raw data blocks, sector trailers excluded |
| `read_ok` | bool | False if any sector failed to authenticate; server then stores the UID only |
| `scanned_at` | ISO 8601 | Device clock from NTP; server time used if missing |
| `fw_version` | string | For the devices page |

**Reliability**

- Offline: if the lookup fails, offer New, Opened and Empty using the product decoded on the device from the raw tag; store chosen events in flash (at least 50) and retry with backoff. A status icon shows the queue size.
- A spool confirmed twice for the same action within 30 seconds sends only one event.
- Heartbeat every 5 minutes so the server can show online/offline. A scanner counts as online when it was seen (heartbeat or scan) in the last 15 minutes.

**Configuration**

- First boot opens a Wi-Fi setup portal (Wi-Fi, server URL, device token).
- The key-derivation constant is entered at provisioning or fetched once from `GET /devices/provisioning` after authentication; it is never in the source repo.
- OTA firmware updates over the LAN.

**Testing without hardware**

- A command-line **scan simulator** (Python) posts the same payload from saved tag dumps, so the server can be built and tested before the hardware exists. It imports dumps exported from a phone and strips the sector trailers, which hold the keys.
- A **screen simulator** runs the firmware's real LVGL screens on a PC at 320×240, with the keyboard as the three buttons and saved tag dumps as taps, against a real or test server.
- Firmware logic reaches the reader, buttons, screen and storage through interfaces, so it can run in PC unit tests with fakes.

## Phone scanner (Android app)

An Android phone can act as one more scanner, so spools can be scanned before the scanner hardware exists, or where it is not at hand. It is a registered device like any scanner, LAN-only, and posts the same scan payload.

**Supported phones**: Android only, and only phones whose NFC chip supports MIFARE Classic (mostly NXP-based, such as Google Pixel phones). Many phones with other NFC chips cannot read these tags; the app checks for MIFARE Classic support and says so plainly when it is missing. iPhones are not supported.

**Build**

- A Capacitor wrapper around the same SvelteKit build as the web app, in a top-level `android/` project.
- A small Kotlin plugin reads a tag with Android's `MifareClassic` API: it reads the UID, derives the 16 keys, authenticates and reads every data block, and returns the UID, the blocks (sector trailers excluded) and `read_ok`. Keys never leave the plugin.
- API requests go through Capacitor's native HTTP, so the server needs no CORS and the web security model is unchanged: the same session cookie and CSRF header.

**What the app shows**

- **Scan**: a screen shown only in the app that mirrors the scanner flow: tap a spool, see the spool card (name, color swatch, state with its date), choose from the same actions with the suggested one highlighted (see User workflows), and see the result. No choice within 15 seconds cancels with no event sent, and the same action confirmed twice for a spool within 30 seconds sends one event.
- **Scan layout** (owner's choice, 2026-11-06; follows `docs/mockups/mobile-scanner/`): everything touched while scanning is in the bottom half of the screen, for one hand.
  - Header: the connection status (Online, Offline or Away, with the queue size when anything is queued), the theme control (the same Light / Dark / System choice as the web app's header), a button to Pairing and a button to the full app.
  - Waiting: a large target, "Hold a spool to the back of your phone", and the last scan with Undo at the bottom.
  - Spool found: the spool's color ring, state chip, name and state date, a bar counting down the 15 seconds, and the action keys in a row with the suggested one marked "Suggested".
  - Result: the action in large type with the spool, and a bar counting down the 3 seconds. Undo, View spool (for a spool the server knows) and Scan next, which goes back to waiting at once.
  - The countdown bars follow the real timers: each new spool or result starts a new bar.
  - Online means the server answered the last request (a heartbeat, lookup, action or undo); Offline means it could not be reached; Away means it answered that the phone is not on the home network (see Away from home). Only the server's own answers count: a page that is not its JSON (Cloudflare Access's sign-in page after a redirect, a proxy's error page, a Wi-Fi sign-in portal) means it could not be reached.
- **Unpacking a delivery** (owner's choice, 2026-11-06): a **Delivery** toggle beside the last scan turns on a list of the spools recorded in this session, for checking off a whole box.
  - The top of the screen is the list, newest at the bottom, with totals ("4 new · 1 opened", and empty when there are any). Each row has the spool's color, name, time and number; a spool still in the offline queue is marked queued; an undone one is marked Undone and leaves the totals.
  - Only the newest row has Undo, matching the single Undo; while its result is on screen, the Undo is in the panel instead.
  - The bottom is one panel that changes with the step: Ready, then the spool with its keys and the 15-second bar, then what was recorded with Undo and the 3-second bar. A tag not tracked yet shows "Not tracked yet", with New suggested.
  - The toggle shows only while waiting, so the mode cannot change halfway through a choice.
  - The list lasts until the app is closed: leaving Scan, or turning Delivery off and on, keeps it. **Clear** empties it; the recorded events stay. Unlinking the phone also clears it.
- **The full web app**: every page, after a normal user sign-in. Scanning uses the device token, not the user's session. In the app, the header has a Scan button (the same phone icon as Scan's target) that goes back to Scan, and the Account page links to the phone's pairing.
- **Start screen** (owner's choice, 2026-11-10): the app opens on the RollCall intro animation (`web/src/lib/assets/rollcall-intro-roll.svg`, from `docs/mockups/logo/`; the spool rolls in and the words follow, about 5 seconds; on the dark theme its words are drawn light) while it loads its pairing, first hears from the server and checks who is signed in. A sign-in check that cannot reach the server (for example a phone woken up before its Wi-Fi is back, which is when Android restarts the app after an update) never sends the user to the sign-in page: the app shows "Cannot reach the server" and checks again when the network returns and every 5 seconds (owner, 2026-11-10). The animation plays through at least one full cycle, so the check is always seen landing, then the screen stays until the app is ready, or 4 seconds at most. The cycle's length is read from the animation itself, so a redesigned animation needs only the new file. With the phone's reduce-motion setting on, the logo is still and the screen ends as soon as the app is ready.
- **Logo and name**: the spool mark (`docs/mockups/logo/rollcall-logo.svg`) is the launcher icon (an adaptive icon on the logo's cream, with a one-colour version for themed icons), the native splash screen before the start screen, the logo in the web app's header and the favicon. The app is named RollCall on the phone, and the web app's header and page titles say RollCall (owner, 2026-11-10: one word, capital C); the rest of the code keeps RollCall until the rename (see Name and rename).
- Scan and Pairing work without a user sign-in, and Scan works without the server (offline). Until the phone is set up the app opens on Pairing. In a browser these two screens only say they belong to the app.
- **Opening screen** (owner's request, 2026-11-10): each phone opens on Inventory ("Looking at stock") or on Scan ("Scanning"). The app asks once, right after the phone is set up by signing in, and the choice can be changed on the Pairing page; it is kept on the phone. A phone paired with a code opens on Scan until changed. Scan is always one tap away in the header.
- Like the scanner's "Last scan", Scan keeps the last scan with an Undo: it reverts the event, or takes it out of the queue if it has not been sent yet. Info shows the AMS remaining % and links to the spool's page.

**Device behavior**

- Scans and undo of its own events use the device token, exactly as the scanner does. A heartbeat is sent every 5 minutes while the app is open.
- Offline, as on the scanner: if the lookup fails, the product, type and color are decoded on the phone from the raw tag, New, Opened and Empty are offered, and chosen actions are queued (at least 50) and retried with backoff. As soon as the server answers again (a heartbeat, which is also sent when the app comes back to the front, or any lookup or action), the whole queue is sent without waiting for the backoff. The `event_id` makes retries idempotent. The Scan screen shows the queue size. A queued scan leaves the queue only when the server accepts or refuses it; not reaching the server, or being away from home, keeps it queued.

**Pairing**

- **Setting up by signing in** (owner's choice, 2026-11-10; the usual way): on first start the app asks for the server's address (the same address rules as pairing, below), then for the user's username and password, as on the web. Once signed in on the home network, the app sets itself up as that user's phone (`POST /devices/mine`, named after the phone's model), fetches the provisioning, and asks for the opening screen. No Admin step and no code. Away from home it says to finish setting up at home (Cloudflare Access stops the app until it has the service token, which the server hands out only at home). "Use a different server" goes back to the address.
- **A user's phone** belongs to them: its scans record the user as well as the phone (Activity shows "user (phone)"), and the user's role decides what it may do. An Editor's or Admin's phone records actions and undoes them; a **Viewer's phone** looks spools up and shows them (Info and Cancel only, with "Your account can look spools up but not record them"), offline too, and records nothing; a disabled user's phone is refused. A role change applies at once. The provisioning tells the phone whether it records. One user may have 5 phones set up at once; unlinking one frees its place. The Devices page shows each phone's owner.
- **Pairing with a code** stays, for a shared phone that belongs to no one: "Pair with a code instead" on the first-start screen.
- Registering a device or rotating its token on the Devices page also shows a QR code, once, holding the server URL, the token and the device ID (scans must name their device). The URL defaults to the address the admin is using and can be changed before the code is shown. The code holds JSON, `{"v": 1, "url": "...", "token": "...", "device_id": "..."}`, so the format can change later.
- The app scans the QR code with the camera; typing the URL and token is the fallback.
- **Unlink this phone** (owner's request, 2026-11-10), on the Pairing page, after a confirmation: the app asks the server to revoke its own token (`POST /devices/unlink`), then forgets the server address, token, key-derivation constant and offline queue on the phone whatever the answer, so a phone whose server is gone can still be unlinked. It says whether the token was revoked; if the server could not be reached, the device is still listed on the Devices page, where an Admin revokes it. The confirmation warns when queued scans would be dropped. An unlinked device stays listed like a revoked one, and rotating its token re-enables it.
- Pairing is reachable without signing in or reaching the server: from Scan's header, from the sign-in page in the app, and from the app's "Cannot reach the server" screen (as well as from the Account page).
- Unlinking a phone also signs the app out and forgets the server's address, since the phone no longer belongs to anyone.
- The token, the key-derivation constant and the Cloudflare Access service token (if the server has one) are stored encrypted with the Android Keystore. The constant and the Access token come from `GET /devices/provisioning` after pairing and are never bundled in the app. The app fetches both again the first time it reaches the server at home after it opens or comes back to the front, so a replaced Access token or salt reaches the phone without pairing again, and an Access token removed on the server is removed from the phone. The app opts out of Android backup, because the Keystore key cannot be restored on another phone; a restored or damaged value reads as missing and the phone pairs again.

**Network**

- The app allows plain HTTP for LAN addresses, like the scanner, and HTTPS everywhere. A LAN address is a private IPv4 or IPv6 address, a name without dots, or a name ending in `.local`, `.lan` or `.home.arpa`; pairing refuses any other `http://` address. Pairing also refuses loopback addresses (`localhost`, `127.x.x.x`, `::1`), on the Devices page and in the app, because on the phone they name the phone itself.
- The session cookie is `Secure`, so signing in over a plain `http://` address works only with `COOKIE_SECURE=false`. Pairing with the HTTPS address is recommended.
- **Same address at home and away** (owner's setup, 2026-11-10): the web app's hostname reaches a reverse proxy on the LAN at home (the home DNS answers it with the server's LAN address, "split DNS"), and Cloudflare's tunnel away from home. The phone keeps one address and one sign-in. At home, scans reach the server through the LAN proxy with the phone's LAN address (the proxy is in `FORWARDED_ALLOW_IPS`); through a tunnel, the server sees a public address, so scanning works only at home. See `docs/deploy.md`.

**Releases and updates** (owner's choice, 2026-11-11)

- Everyday phones run the **release app**, RollCall, with the app ID `io.github.sirmeili.rollcall`. Development builds are **RollCall (dev)**, `io.github.sirmeili.rollcall.debug`, version `dev`, and install next to it, each with its own pairing.
- A release is published by pushing a tag `app-v<major>.<minor>.<patch>` (each part 0 to 99) on a commit in `main`. A workflow builds the app at that version (version code `major·10000 + minor·100 + patch`, so each release is higher than the last), runs the Kotlin tests, signs it with the release key, checks the app ID, version and signature (and the certificate, when its SHA-256 is set as the repository variable `RELEASE_CERT_SHA256`), and attaches `rollcall-<version>.apk` to a GitHub Release named "RollCall app <version>" with the APK's and the certificate's SHA-256.
- The release key is the owner's: it is kept outside the repository and reaches the workflow only as the secrets `ANDROID_KEYSTORE_BASE64` and `ANDROID_KEYSTORE_PASSWORD`. Every release uses the same key, since Android refuses an update signed by another. CI builds a test release on every pull request with a key made for that run.
- Phones get releases with **Obtainium**, which watches the repository's releases and offers each new version; Android keeps the app's data across updates, so the phone stays set up. The steps are in `android/README.md`.
- The Account page shows the app's version in the app ("RollCall app 1.2.0"); the heartbeat reports it, as on the Devices page.

**Away from home** (owner's request, 2026-11-10)

- The pages work away from home: browsing the inventory is what the app is for there. Scanning stays on the home network: away from home a scan is decoded on the phone and queued, as when the server is down, and the queue is sent when the phone is home again. The Scan header shows Away.
- The server marks its refusal of a bearer token from outside `TRUSTED_NETWORKS` with the header `X-Rollcall-Refused: local-network-only`, so the app can tell "away from home" from a revoked or refused token.
- **Cloudflare Access**: the app cannot use Access's sign-in page, so it sends a Cloudflare Access service token (`CF-Access-Client-Id` and `CF-Access-Client-Secret`) with every request to the paired server, its pages and its scanner requests alike. An Admin enters the token once on the Settings page (Scanners); the server hands it to paired phones with the salt, on the LAN only. One token serves every phone (owner's choice): to replace it, make a new one in Cloudflare, save it on the Settings page, and keep the old one in the Access policy until every phone has been home once. The app sends it only over HTTPS. RollCall's own sign-in and device tokens still apply behind Access.

## Server: data model

The server is event-sourced: every scan, AMS observation and UI edit is an immutable event, and each spool's current state is derived from its events. This makes undo and audit trivial.

**Stack**: Python 3.12, FastAPI, SQLAlchemy with SQLite (WAL mode), Alembic migrations, a SvelteKit web app (TypeScript, built as static files and served by FastAPI), one Docker image.

**Tables**

| Table | Key fields | Purpose |
| --- | --- | --- |
| `product` | id, material\_id, variant\_id, filament\_type, color\_rgba, display\_name, low\_stock\_threshold, nearly\_out\_pct, provisional, from\_ams | One row per filament product (for example Black PLA Basic); created automatically from the first decoded tag; display name editable. `nearly_out_pct` (default 15) is the AMS remaining % at or below which an open spool is shown as nearly out. Provisional products (from the AMS or manual entry) have no variant ID until a tag is scanned; one made from the AMS keeps the AMS's material ID and has `from_ams` set |
| `spool` | id, tray\_uid (unique, null for a manual placeholder), product\_id, state, received\_at, opened\_at, emptied\_at, remaining\_pct, location, notes, likely\_empty\_dismissed\_at | One physical spool; state and timestamps derived from events. State is null (Unknown) when every event that set it has been undone. `likely_empty_dismissed_at` hides its "Likely empty" suggestion |
| `tag` | uid (unique), spool\_id, raw\_blocks, decoded\_json, first\_seen\_at, dismissed\_at | Each spool has up to two tags; raw dump kept for re-decoding. `dismissed_at` hides an `unidentified` tag from Review |
| `event` | id (UUID from device or server), spool\_id, type, source, device\_id, user\_id, occurred\_at, flagged, reviewed\_at, reviewed\_by, payload\_json, reverted\_by | Append-only log; undo writes a new `revert` event. `user_id` records who acted in the web app |
| `device` | id, name, token\_hash, revoked\_at, last\_seen\_at, fw\_version, queue\_length | Registered scanners; firmware version and offline queue length come from the last heartbeat |
| `user` | id, username (unique, case-insensitive), password\_hash, role, disabled\_at, last\_login\_at | Web app accounts; see Users and roles |
| `session` | id, token\_hash, user\_id, expires\_at, last\_seen\_at | Signed-in browsers; only a hash of the cookie value is stored |
| `printer` | id, name, serial, host, port, access\_code (encrypted), cert\_sha256, last\_report\_at | Printers watched over MQTT, added on the Devices page or seeded once from `PRINTERS`. `cert_sha256` is the pinned TLS certificate fingerprint |
| `setting` | key, value (encrypted for secrets), updated\_at, updated\_by | Values saved in the app; no row means the `.env` value or the default is used |
| `machine_token` | id, name, role, token\_hash, created\_by, created\_at, last\_used\_at, revoked\_at | Bearer tokens for Home Assistant and scripts, accepted only from the LAN |
| `printer_slot` | id, printer\_id, ams\_index, tray\_index, tray\_uuid, spool\_id, filament\_type, color\_rgba, remaining\_pct, updated\_at | What the AMS last reported in each slot, and the spool it is. `ams_index` is the printer's unit ID: 0 to 3 for an AMS, 128 and up for an AMS HT |

**Spool states and transitions**

| From | Event | To | Source |
| --- | --- | --- | --- |
| (none) | `received` | `sealed` | Scanner, UI (manual entry creates a placeholder) |
| (none) | `opened` | `open` | Scanner, UI, AMS (implicit receive) |
| `sealed` | `opened` | `open` | Scanner, UI, AMS first sighting |
| `open` | `empty` | `empty` | Scanner, UI |
| `sealed` | `empty` | `empty` | Scanner, UI (flagged for review) |
| any | `revert` | previous state (Unknown if no events remain) | Undo from scanner or UI |
| `empty` | `opened` | `open` | UI (correction); queued offline scan (flagged for review) |
| `open`, `empty` | `received` | unchanged | Queued offline scan, UI (flagged for review) |

**Decoding**

- A `decoder` module turns raw blocks into a typed record (material, variant, type, color, weight, diameter, temperatures, production date, tray UID).
- Decoding is pure and versioned; if the decoder improves, a maintenance command re-decodes every stored tag.
- Unknown or unreadable tags are stored in `tag` by UID with no spool and shown in Review as `unidentified`, so nothing is lost.

## Server: API

A versioned REST API under `/api/v1`, documented by FastAPI's generated OpenAPI page (LAN only). Scanners authenticate with a device token, and Home Assistant and scripts with a machine token (or `ADMIN_TOKEN`); bearer tokens are accepted only from the LAN. The web app uses a session cookie, and each route requires a minimum role (see Users and roles).

| Method | Path | Caller | Purpose |
| --- | --- | --- | --- |
| POST | `/auth/login`, `/auth/logout` | Web app | Sign in with username and password; sign out |
| GET | `/auth/me` | Web app | Current user and role |
| POST | `/auth/password` | Viewer | Change own password; ends the user's other sessions |
| POST | `/scans` | Scanner | Submit a scan event; a lookup returns spool, product, state, allowed and suggested actions; an action returns the new state and a `feedback` code for the screen |
| POST | `/devices/heartbeat` | Scanner | Online status, firmware version, queue length |
| POST | `/devices/mine` | Web app (any role), home network only | The phone app sets itself up as the signed-in user's phone; returns the device token once. Refused away from home (marked `X-Rollcall-Refused: local-network-only`), past 5 active phones, or without the write header |
| POST | `/devices/unlink` | Scanner | The calling device revokes its own token (the phone app's Unlink this phone) |
| GET | `/devices/provisioning` | Scanner | Returns the key-derivation constant to an authenticated device (scanner firmware and the phone app), the Cloudflare Access service token when one is set, and whether the device records actions (`records`, false for a Viewer's phone) |
| GET | `/inventory` | Viewer, HA | Counts by product and state, low-stock flags, and each open spool's remaining % with a nearly-out flag |
| GET | `/spools` | Viewer | List with filters (state, product, filament type, location) and search |
| POST | `/spools` | Editor | Manual entry: create a placeholder spool for a product, with a `received` event |
| GET | `/spools/{id}` | Viewer | Spool detail with tags and event timeline |
| PATCH | `/spools/{id}`, `/spools` | Editor | Edit location and notes; bulk change location |
| POST | `/spools/{id}/events` | Editor | Manual action (received, opened, empty) |
| GET | `/events` | Viewer | Activity: all events, newest first, paged; filter by spool or source (scanner, web app, printer) |
| POST | `/events/{id}/revert` | Editor, Scanner | Undo an event; a scanner can undo only events from its own device |
| GET | `/review` | Viewer | Flagged events not yet reviewed, `unidentified` tags, likely-empty suggestions |
| POST | `/review/spools/{id}/dismiss`, `/review/spools/{id}/restore` | Editor | Dismiss a likely-empty suggestion; Bring back returns it |
| GET | `/printers` | Admin | Printers with online status, certificate pin state and each AMS slot's contents and spool |
| POST | `/printers/{id}/unpin` | Admin | Forget the pinned certificate, so the next connection pins a new one (for example after a firmware update) |
| POST | `/review/events/{id}/accept` | Editor | Mark a flagged event as correct |
| POST | `/review/tags/{uid}/dismiss` | Editor | Hide an `unidentified` tag from Review |
| POST | `/review/events/{id}/unaccept`, `/review/tags/{uid}/restore` | Editor | Bring back: return an accepted event or a dismissed tag to Review |
| GET / POST / PATCH | `/products`, `/products/{id}` | Viewer (GET), Editor | Display names, low-stock thresholds and nearly-out %; POST creates a provisional product for manual entry |
| GET / POST / DELETE | `/devices`, `/devices/{id}` | Admin | Register a scanner and issue or revoke its token |
| POST | `/devices/{id}/rotate` | Admin | Issue a new token, invalidating the old one; also re-enables a revoked scanner |
| GET / POST / PATCH | `/users`, `/users/{id}` | Admin | List and create users, change role, disable, reset password |
| POST / PATCH / DELETE | `/printers`, `/printers/{id}` | Admin | Add, edit and remove a printer; the access code is write-only |
| GET / PUT | `/settings/{group}` | Admin | Read and change app settings by group (`general`, `home-assistant`, `scanners`). Each value says where it comes from (`env`, `app` or `default`); secrets read back only as set or not set |
| DELETE | `/settings/{group}/{key}` | Admin | Go back to the `.env` value (or the default) for one setting |
| POST | `/settings/home-assistant/test`, `/printers/{id}/test` | Admin | Try the saved or entered values once and report the result, without repeating secrets |
| GET / POST / DELETE | `/tokens`, `/tokens/{id}` | Admin | Machine tokens for Home Assistant and scripts: named, with a role, shown once, revocable |
| GET / POST | `/setup` | LAN, with the setup code to POST | First-start setup: whether it is open; create the first admin and the starter settings, which closes it for good |
| GET | `/health` | Docker, HA | Liveness and dependency status |

**Scan response feedback codes**: `ok`, `ok_created` (implicit receive), `already_in_state`, `flagged` (out of order), `unreadable`, `error`. The device maps each to a screen message and sound.

**Idempotency**: a repeated `event_id` returns the original result without writing a second event.

## Users and roles

The web app has personal accounts, so a few people can use it from anywhere, some only to look.

| Role | Can |
| --- | --- |
| Viewer | See every page: inventory, spools, products, review, activity |
| Editor | Also record actions, undo, edit spools and products, add spools by hand, resolve review items |
| Admin | Also manage users, scanners, printers, machine tokens and settings |
| Requester (Phase 2, planned) | Only submit print requests, follow their own, and browse the filament in stock and the catalog; no other page. See Future enhancements: print requests |

- Accounts are created by an admin; there is no sign-up. The first admin is created during first-start setup (see Settings and first start) or from the command line with `ft-admin create-user`, so there is never a default account. `ft-admin reset-password` recovers an account when no admin can sign in.
- Passwords are at least 12 characters and stored as Argon2id hashes. Users can change their own; an admin can reset one or disable an account.
- Signing in sets a session cookie (HttpOnly, Secure, SameSite=Strict) valid for `SESSION_DAYS`. Sessions end on sign-out, on a password change (other sessions), or when the account is disabled.
- **A session in use stays alive** (owner's choice, 2026-11-10): when less than half of `SESSION_DAYS` is left, the next request renews it to the full `SESSION_DAYS` with a fresh cookie. Only a session unused for `SESSION_DAYS` ends by itself, so the phone app does not ask for the password every month.
- Events recorded in the web app, and scans from a user's own phone, store who made them, and the Activity page shows it.

## Settings and first start

Most settings live in the app, so a deployment needs only a short `.env` file (owner's choice, 2026-11-07).

**Where each setting lives**

- **In the app** (Admin › Settings, and printers on the Devices page): the Home Assistant settings (MQTT broker, user and password, discovery prefix, HA URL and token), printers (name, host, port, serial, access code), `BAMBU_KDF_SALT`, the time zone and `SESSION_DAYS`. Machine tokens made in the app replace `ADMIN_TOKEN` for Home Assistant and scripts.
- **Only in `.env`**: `SETTINGS_KEY`, the database location, `WEB_DIR`, `TRUSTED_NETWORKS`, `FORWARDED_ALLOW_IPS` and `COOKIE_SECURE`. A mistake in these could lock the admin out, or open LAN-only routes to the internet, with no way back through the app.
- **Precedence**: a value in `.env` is the starting value. Once an admin saves a value in the app, the app's value is used. The Settings page shows where each value comes from (`.env`, the app or the default), and "Use the .env value" goes back to it. `PRINTERS` in `.env` adds its printers once, the first time the server sees them; after that they are edited in the app.
- Changes apply without a restart: saving the Home Assistant settings reconnects the MQTT link and the event sender, and saving a printer reconnects that printer. Changing a printer's host or port keeps its certificate pin, so a different certificate is refused and shown as usual.
- `ADMIN_TOKEN` in `.env` keeps working, so existing setups do not break.

**Secrets**

- Passwords, tokens, access codes and the salt are stored encrypted (AES-256-GCM, a fresh nonce per value, the setting's name as associated data) with the key from `SETTINGS_KEY`. If it is unset, the server creates a random key file beside the database on first start, readable only by the server's user.
- The API never returns a stored secret, only whether one is set. Saving with a secret field left empty keeps the current value; a separate Clear removes it.
- Encryption protects copies of the database, such as backups. It does not protect against someone who can read the server's disk, where the key file also is; set `SETTINGS_KEY` in the environment to keep the key off the database volume. A database moved to another server without its key keeps everything except the stored secrets, which the Settings page then asks for again.
- Each settings change is logged with who made it and which setting, never the value.

**First-start setup**

- While no admin account exists, the web app shows a Setup page instead of the sign-in page. It creates the first admin (same password rules as any account) and asks for the starter settings: the time zone and `BAMBU_KDF_SALT`, both optional and skipped when already set in `.env`.
- Setup answers only from `TRUSTED_NETWORKS`, so it cannot be reached through the reverse proxy.
- Setup also needs a one-time setup code. While setup is open, the server makes a new random code at each start and writes it to its log, so only someone who can see the server's log can finish setup. Wrong codes are throttled like sign-ins.
- Once an admin exists, setup is closed for good. `ft-admin` stays for recovery.

## Server: web UI

A small, mobile-friendly web app for checking stock and fixing mistakes; day-to-day input comes from the scanner. It is a SvelteKit single-page app built to static files, so production needs no Node.js. Controls a user's role does not allow are hidden, and the API enforces the same rules. The look follows the mockups in `docs/mockups/web/`, and on phones `docs/mockups/mobile-web/`. The theme, Light, Dark or System (follow the device), is chosen on the Account page and remembered on each device (owner, 2026-11-10: each phone and browser keeps its own).

**Phone layout** (owner's choice, 2026-11-10; follows `docs/mockups/mobile-web/`): at 600px wide or less (the phone app, or a narrow browser) the header is replaced by:

- **A top bar** with the RollCall mark (a link to Inventory) and the page title, nothing else. The page's own heading stays for screen readers.
- **A bottom bar** on every page but Scan: **Menu** at the left, a raised round **Scan** button in the centre (only in the Android app), and the signed-in user (initial and name) at the right, who opens Account. Menu shows a dot while Review has items waiting.
- **The menu**: a sheet that rises from the bottom over a dimmed page, with large buttons for Inventory, Spools, Products, Review (with its count) and Activity, then an Admin row of Devices, Users and Settings. Pages the user's role does not allow are hidden, and the current page is filled in. The Menu button turns into Close while it is open; the dimmed page, Escape, Close or choosing a page closes it, and the focus stays in the sheet while it is open.

Wider screens keep the header with the pages across the top; Scan keeps its own one-handed layout at every size.

| Page | Shows | Actions |
| --- | --- | --- |
| Inventory | Only products on hand (at least one sealed or open spool; used-up spools stay on Spools and the product on Products), each with color swatch, name, sealed / open / used-up counts, low-stock badge (sealed count at or below the product's threshold; 0 turns it off), and a remaining % bar for each open spool, marked nearly out at or below the product's nearly-out %. Totals of sealed, open and used-up spools with the count shown ("All 11" or "5 of 11"). Wider screens show cards (totals on one line above them) or a list (totals under the column headings), the choice remembered on the device. On a phone, compact rows with the totals in the header; tapping a row expands it in place, one at a time, to show each open spool's bar ("None open" when none), the low-stock rule, the status (LOW · ≤N, OK or Alert off), the source (From tag or Added by hand), and View spools (Spools searched for the product) and Edit product | Search by name or color; Low stock and Nearly out quick filters, each with its count; a filter sheet with types (those on hand, most common first, several at once; picking every type is picking none), Low stock only, and the sort (Low first, Name, Most stock; Name by default), applied with Show N products. The Filter button turns dark and shows how many filters are on; picked types show as one chip ("PLA, PETG", "All but ABS" or "5 types") with ✕, then Clear. Filters are not saved. Cards or list on wider screens (owner, 2026-11-10) |
| Spools | Table of spools with state, product, location (and AMS slot while loaded), remaining %, dates | Filter by state and type, search, bulk change location, add a spool by hand |
| Spool detail | Tag data, AMS remaining % and grams left (remaining % of the tag's spool weight), the AMS slot while loaded (for example "AMS 1, slot 2 on P1S"), event timeline | Manual action, undo, edit notes and location |
| Products | Decoded product IDs and colors | Set display name, low-stock threshold and nearly-out % |
| Review | Flagged events, `unidentified` tags, "likely empty" suggestions | Flagged event: Accept (it was right), Undo (revert it) or Open spool (fix by hand). Unidentified tag: dismiss. Likely empty: mark used up or dismiss. After an Accept or a dismiss, Bring back returns the item to Review |
| Devices | Scanners (including phones) and printers with online status, firmware, queue; each printer shows its AMS slots and the spool in each, and warns when its certificate does not match the pin | Register device (token shown once, with a QR code for the phone app), rotate token, revoke; add, edit, test and remove a printer; forget a printer's certificate pin |
| Users | Accounts and roles (Admin only), with a short description of what each role can do | Create, change role, reset password, disable |
| Settings | App settings by group (Admin only): General (time zone, sign-in length), Home Assistant, Scanners (the key-derivation salt) and machine tokens; each value shows where it comes from | Save, Test (Home Assistant), Use the .env value, create and revoke machine tokens (each shown once) |
| Setup | First-start setup, shown only until the first admin exists | Create the first admin and the starter settings, with the setup code |
| Account | The signed-in user | Appearance (Light, Dark or System, saved on this device), Change password (opens the form, with a meter showing progress to the 12-character minimum), This phone (in the phone app: whether it is set up, linking to Pairing), sign out |
| Activity | Global event log, newest first, grouped by day | Filter by source (scanners, web app, printer); undo |

The color swatch comes from the tag's RGBA value, so new colors appear correctly with no setup.

## Integrations

**Bambu P1S (local MQTT)**

- The server keeps one MQTT connection per configured printer (TLS, port 8883 by default, user `bblp` and the LAN access code), subscribes to `device/{serial}/report` and reconnects with backoff.
- P1 printers report only what changed, so the server merges each message into its full view of every AMS tray. From each tray it reads the tray UID, material ID (`tray_info_idx`), filament type, color and remaining %. See Automatic detection from the AMS for what this does to spools.
- The report's `tray_uuid` is the tag's tray UID (checked on a P1S), so the AMS and the scanner identify a spool the same way. Its `tag_uid` starts with the tag's 4-byte UID and is not used.
- Units 0 to 3 are AMS units with four slots each, shown as AMS 1 to AMS 4. An AMS HT has one slot and a unit ID from 128, and is shown as AMS HT 1, AMS HT 2 and so on. The external spool holder (`vt_tray`) is not read.
- Read-only, with one exception: the server publishes `pushall`, which requests full state, on connect and every 30 minutes. It never publishes anything else to the printer.
- A printer is online when it reported in the last 5 minutes.
- **Certificate pinning**: the printer's TLS certificate is not from a public authority, so the server pins it on first use. The first connection only completes a TLS handshake and stores the certificate's SHA-256 fingerprint; every connection after that trusts only the pinned certificate, so the access code is never sent to anything else. A different certificate is refused and shown on the Devices page, where an admin can forget the pin (for example after a firmware update).
- Printers are added and edited on the Devices page; `PRINTERS` in `.env` seeds them (see Settings and first start).
- **MQTT proxies**: a printer may point at an MQTT proxy instead of the printer, to stay under the printer's connection limit. A proxy such as `bambu-mqtt-proxy` speaks the same protocol (TLS on 8883 with its own certificate, user `bblp`, the access code, the same topics, and it forwards `pushall`), so it needs no special support: set its host and port, and use the alias as the serial if the proxy renames the printer. The pin is then the proxy's certificate. Any proxy is a separate project, not part of this system.
- A **fake printer** replays recorded or documentation-based report messages over TLS, so this integration can be tested without a printer.

**Home Assistant**

- Publish entities through MQTT discovery to the existing broker, under one device "RollCall", with five entities (owner's choice, 2026-11-06: a few totals rather than entities per product):
  - **Total spools**: sealed and open spools, not used up;
  - **Total open** and **Total sealed**;
  - **Low filament**: a binary sensor, on while any product is low on stock (sealed count at or below its threshold), with attributes `count` and `products`, a list of the low products (name, type, color, sealed count, threshold);
  - **Spools in review**: the Review page's count.
- Because Low filament stays on when a second product goes low, automations that should act on each product use the `filament_tracker_low_stock` event instead.
- The server clears retained discovery messages under its own node ID that it no longer publishes (for example, entities from an earlier version), which removes them from Home Assistant.
- Entities are published retained and updated within about 5 seconds of any change, whatever made it. The server reads its stock every 5 seconds and publishes only what changed.
- While the server is stopped or cannot reach the broker, the entities are unavailable: the server publishes `online` and `offline` on an availability topic, with `offline` as its MQTT will.
- When Home Assistant restarts (its `online` birth message), everything is published again.
- `/health` reports the MQTT link as `off`, `connecting`, `connected` or `disconnected`.
- The broker and Home Assistant settings are set on the Settings page, starting from `.env`; see Settings and first start.
- Fire HA events through the REST API (`POST /api/events/<type>` with the HA token) for automations:
  - `filament_tracker_spool_received`, `filament_tracker_spool_opened` and `filament_tracker_spool_emptied`, for each such event from any source (scanner, phone, web app, printer), with `event_id`, `spool_id`, `product_id`, `product`, `filament_type`, `color` (`#RRGGBB`), `state`, `source`, `flagged` and `occurred_at`;
  - `filament_tracker_low_stock`, when a product goes from not low to low, with `product_id`, `product`, `filament_type`, `color`, `sealed` and `threshold`. It fires again only after the product has recovered and gone low again.
- Events are read from the database every 5 seconds. Only events recorded after the server started are fired, so a restart never replays history. An event undone before it is fired is skipped; one undone later stays fired. Products already low when the server starts do not fire.
- A failed request is retried after 1, 4 and 15 seconds and then dropped with a warning; a refused token (401 or 403) is not retried. Redirects are not followed, so the token is sent only to the configured HA URL.
- `/health` reports events as `off` (no HA URL and token), `ready` or `failing` (the last event could not be sent).
- Example automation, in `docs/home-assistant/low-stock-automation.yaml`: on low stock, add the product to the shopping list and notify a phone.
- Any automations or scripts created for this project get the `Claude` label.

**Spoolman (optional, later)**

- One-way sync of spools and states into Spoolman, using the tray UID as the lot number. Off by default.

## Security and deployment

**Deployment**

- One Docker image for x86-64 (`linux/amd64`), `ghcr.io/sirmeili/rollcall`, run with Docker Compose on the owner's home server; SQLite database on a mounted volume. GitHub Actions builds the image on every pull request and pushes it to the GitHub Container Registry on each merge to `main`, tagged `latest` and with the commit. The package is private, so the server logs in to `ghcr.io` with a read-only token to pull it.
- The web app may be exposed to the internet, but only through an HTTPS reverse proxy the owner runs (for example Caddy, Nginx Proxy Manager, Traefik or a Cloudflare Tunnel). The app itself speaks plain HTTP to the proxy and trusts forwarded client addresses only from `FORWARDED_ALLOW_IPS`.
- Scanner routes, bearer tokens (device and admin) and the API docs are accepted only from `TRUSTED_NETWORKS`, so they stay on the LAN even if the proxy forwards everything. The proxy should forward only the web app and `/api/v1` anyway.
- Nightly SQLite backup (online backup API) at 03:00 in the server's time zone, to a second volume (`BACKUP_DIR`), 14 kept. Backup files are named by their UTC time. The settings key is never copied into the backups, so the secrets in a backup stay encrypted. `ft-admin backup` makes one at once, for example before an upgrade.

**Configuration** (environment variables or a `.env` file, never committed). Settings marked *app* can also be set in the app, where a saved value wins; see Settings and first start.

| Setting | Example | Purpose |
| --- | --- | --- |
| `ADMIN_TOKEN` | random 32 bytes | Machine access for Home Assistant and scripts, from the LAN only; machine tokens made in the app replace it, and it keeps working if set |
| `SETTINGS_KEY` | random 32 bytes, base64 | Encrypts the secrets stored in the app. Unset: a key file is created beside the database |
| `BAMBU_KDF_SALT` | hex string | *app*. Key-derivation constant, served to provisioned devices |
| `CF_ACCESS_CLIENT_ID`, `CF_ACCESS_CLIENT_SECRET` | `….access`; the secret as Cloudflare gives it: `cfast_` and 48 letters and digits (since 2026-08-26), or 32 to 128 letters and digits (older tokens) | *app*. A Cloudflare Access service token, handed to paired phones so the app passes Access away from home. Unset: none |
| `PRINTERS` | `[{"name": "P1S", "host": "192.168.1.40", "serial": "01P00A...", "access_code": "..."}]` | *app*, seeded once. Printers to watch over MQTT, as a JSON list; each entry may also set `port` (default 8883). `host` and `port` may be an MQTT proxy's |
| `MQTT_URL`, `MQTT_USER`, `MQTT_PASSWORD` | `mqtt://homeassistant.local:1883` | *app*. Home Assistant's MQTT broker, for discovery and state publishing; `mqtts://` for TLS. Unset: nothing is published. The URL must not hold the password |
| `HA_DISCOVERY_PREFIX` | `homeassistant` | *app*. Home Assistant's MQTT discovery prefix |
| `HA_URL`, `HA_TOKEN` | `http://homeassistant.local:8123`, long-lived token | *app*. Home Assistant's address and a long-lived access token, for firing events. Unset: no events are fired. The URL must not hold a user name or password |
| `TZ` | `America/New_York` | *app*. The time zone for every time the web app shows, whatever the viewer's device uses, and for the nightly backup. An IANA name; defaults to `UTC` |
| `TRUSTED_NETWORKS` | `192.168.0.0/16,10.0.0.0/8` | LAN ranges allowed to use bearer tokens, scanner routes and API docs; defaults to the private ranges |
| `FORWARDED_ALLOW_IPS` | `192.168.1.5` | Address of the reverse proxy whose `X-Forwarded-For` is trusted |
| `SESSION_DAYS` | `30` | *app*. How long a web sign-in lasts |
| `COOKIE_SECURE` | `true` | Set `false` only to sign in over plain HTTP on the LAN during development; production is HTTPS |
| `WEB_DIR` | `/app/web` | The built web app; defaults to `web/build` in a source checkout |
| `DATABASE_URL` | `sqlite:////data/filament.db` | The SQLite database; defaults to `data/filament.db` beside the server |
| `BACKUP_DIR` | `/backups` | Where the nightly backups go. Unset: no backups (the Docker image sets it) |

**Security requirements**

- Every endpoint except `/health`, `/auth/login`, `/auth/logout` (which only ends the caller's own session, if any) and `/setup` (LAN only, needs the setup code, and only until the first admin exists) requires authentication, and each enforces a minimum role.
- Sign-in attempts are throttled per username and per client address (HTTP 429), and failures give the same message whether the username exists or not.
- State-changing requests made with a session cookie must carry the `X-Requested-With: filament-tracker` header, which other sites cannot send, in addition to SameSite cookies.
- Responses carry a Content Security Policy, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` and a strict referrer policy.
- Device tokens are stored hashed, revocable, and scoped to `/scans`, `/devices/heartbeat`, `/devices/provisioning`, `/devices/unlink` (which revokes only the caller's own token) and `/events/{id}/revert` for events from that same device.
- Input validation on all payloads (Pydantic); block arrays capped in size. A refused request's answer says where and what is wrong, never the value sent, which may be a password, token or access code.
- No tag UIDs or derived keys in logs above debug level, in line with the RFID guide's request not to publish UID/key pairs.
- Secrets saved in the app are encrypted at rest and never returned by the API (see Settings and first start). Machine tokens are stored hashed, like device tokens. The setup code is written to the log once per start while setup is open, and nowhere else.
- The printer access code, HA token, MQTT password, `BAMBU_KDF_SALT` and the Cloudflare Access client secret never appear in logs, and a rejected setting's error message does not repeat its value. The salt and the Access token are returned only by `/devices/provisioning`, to a device token from the LAN; the settings API never returns the client secret.
- The printer access code and HA token never leave the server or appear in API responses or logs. The access code is sent only to a printer (or proxy) whose certificate matches the pin.

## Testing

The server is fully testable without hardware. Firmware logic is unit tested on a PC, and hardware behavior gets a short manual checklist.

| Layer | What is tested | How |
| --- | --- | --- |
| Decoder | Every field; two rolls of the same product yield the same product key | pytest against generated tags in CI, plus own spools and the public Bambu RFID library locally |
| State machine | Every transition in the table, out-of-order flags, undo | pytest, property tests for event replay |
| API | Auth on every route, idempotent scans, validation errors | pytest with FastAPI TestClient |
| Security | Setup refused from outside the LAN, with a wrong code or once an admin exists; stored secrets never returned or logged, and unreadable without the key; machine tokens limited to their role and refused once revoked; unauthenticated access refused, role checked on every route, revoked tokens and ended sessions refused, sign-in throttling, bearer tokens refused from outside the LAN, CSRF header, security headers, oversized payloads rejected | pytest security suite, run in CI |
| Web app | Components, API client, role-based visibility | Vitest with Testing Library; 90% coverage; `svelte-check` and `npm audit` in CI |
| Web end to end | Sign in as each role, inventory, record and undo an action, review | Playwright against the real server with a database seeded by the scan simulator |
| Phone app | Scan flow, offline queue, on-phone decode, pairing | Vitest; 90% coverage |
| Phone NFC plugin | Key derivation (matching the server), block assembly, trailer stripping, encrypted storage | Kotlin unit tests with a fake tag; 90% line coverage (JaCoCo), excluding the Android glue that needs a phone: `FilamentTrackerPlugin` (NFC reader mode, camera, Capacitor calls), `AndroidMifare`, `KeystoreKey`, `PrefsValues` and `MainActivity` |
| Phone on hardware | Reading on a real phone, MIFARE Classic detection, QR pairing, offline queue, sign-in | Manual checklist per release |
| AMS ingest | Report messages produce the right events | Fake printer replaying recorded or documentation-based messages, including a report captured from a P1S with its identifiers replaced |
| Printer on hardware | Connection and pin, every AMS and AMS HT slot, tray UID matching a scanned tag, automatic Opened, remaining % | `ft-printer check` and a manual checklist, before a release that changes the printer link |
| Home Assistant on hardware | The five entities and their values, unavailable on stop, back after a Home Assistant restart, events, the low-stock automation, the Settings page Test and Save | `ft-ha check` and a manual checklist, before a release that changes the Home Assistant link |
| End to end | Scan simulator drives Received, Opened, Empty for a spool; HA entities update | Docker Compose test stack with a Mosquitto container |
| Firmware logic | Screen flow, tag parsing, offline queue, dedupe, button thresholds | PC unit tests with fakes; 90% coverage, excluding a named list of hardware drivers |
| Firmware screens | Every screen and soft-key mapping | Screen simulator |
| Firmware on hardware | Read through lid and box, each soft key and touch target, menu navigation, timeout, offline queue, OTA, plus the excluded drivers | Manual checklist per release |

Public and personal tag dumps contain UIDs and keys. They are used locally and never stored in the repo; CI uses generated tags only.

`AGENTS.md` in the repo sets the build guardrails: work only from this spec, tests and security tests with every change, feature branches, and spec changes committed with the work they cover.

## Milestones

Each milestone ends with something usable. Reading is proved first with a phone, so the software can be built before the scanner hardware arrives; the PN532 proof follows when it does.

1. **M0a Prove reading, phone**: dump two rolls of the same product with an Android app; confirm matching product fields and distinct tray UIDs; try reading through the shipping box.
2. **M1 Server core**: decoder, data model, event log, `/scans` API, scan simulator, tests.
3. **M2 Web UI**: user accounts and roles, inventory, spools, spool detail, products, review, activity, devices, users, manual entry.
4. **M5 Printer link**: P1S MQTT ingest, automatic Opened, remaining %, likely-empty suggestions, built against the fake printer and checked against the real P1S.
5. **M8 Phone scanner**: Android app (Capacitor around the web app, with a Kotlin NFC plugin), QR pairing on the Devices page, `/devices/provisioning`, offline queue.
6. **M6 Home Assistant**: MQTT discovery entities, events, low-stock automation, and the Settings page with the Home Assistant settings in the app.
7. **M9 Deployment**: printers and the remaining settings in the app, machine tokens, first-start setup, the Docker image and Compose file, nightly backups.
8. **M10 Print requests, Phase 2**: the filament catalog and color codes, the Requester role, print requests and their status pipeline, holding filament, the shopping list. See Future enhancements: print requests.
9. **M11 Print requests, Phase 3**: reading 3MF files, print jobs from the printer, push notifications, picking colors on the model, the MCP server.
10. **M3a Firmware without hardware**: scan flow, offline queue and dedupe logic with PC tests, screen simulator.
11. **M0b Prove reading, PN532**: repeat the read tests on the bench rig and measure reading through the 1 mm lid and shipping box.
12. **M3b Firmware on hardware**: breadboard build, real drivers, provisioning, OTA.
13. **M4 Enclosure**: printed case, button labels, antenna placement, final wiring.
14. **M7 Later**: see Future enhancements, including the Later items of print requests.

## Future enhancements

- **Custom PCB scanner (v2)**: replaces the CYD prototype once the screen and menu flow are settled. ESP32-S3 module, PN532 and a tuned antenna on board, SPI touch TFT, three dedicated button inputs (no resistor ladder), front-facing RGB LED, buzzer, and USB-C power with an optional PoE variant, following the Harmony Hub replacement PCB work.
- **Load-cell scale**: weigh a spool for remaining grams when it is not in the AMS.
- **Spoolman sync**: one-way export, as described under Integrations.
- **Non-Bambu filament**: NTAG stickers in an open format, or QR labels printed by the server.
- **Second scanner by the printer**: same firmware, its own device token.

## Future enhancements: print requests

None of this is built or scheduled inside the current milestones, and none of it changes them. It turns the inventory into a combined inventory and print request tool. The owner's brother co-owns the printer, which lives at the owner's house, and today he sends models through a Google Form. With accurate stock, a request can offer the filaments actually on the shelf, and the full Bambu catalog when a color is missing, which feeds a shopping list. Phase 2 and Phase 3 come after M9 and before the firmware milestones (the phone scans until then); Later comes after them. The owner's decisions (2026-11-07) are below; items whose claims were checked end with what was found, and the full list is under Verification findings.

### Name and rename

- **Working name: RollCall** (owner, 2026-11-09; it replaced the earlier working name Spoolhouse). It is not final and may change. The spec uses it from now on, written RollCall, one word (owner, 2026-11-10), and so does every name people see. The code's identifiers (below) keep `filament_tracker` and similar until the rename is done as its own piece of work, after the name is settled. The repo was renamed to `sirmeili/rollcall` and the Docker image uses `rollcall` from the start (M9), since both were cheap to name now.
- **What a rename touches**, and what breaks (the owner accepted reinstalling the phone app and renaming the Home Assistant names, since everything so far is testing):

| Area | Today | Effect of renaming |
| --- | --- | --- |
| GitHub repo | **Done (2026-11-09)**: `sirmeili/rollcall`, was `sirmeili/filament-tracker` | Safe: GitHub redirects the old URL while no new repo takes the old name. The git remote, README links and the 3D viewer links were updated |
| Python package, project and commands | `filament_tracker`, `ft-admin`, `ft-sim`, `ft-printer`, `ft-fakeprinter` | Safe in code; every documented command changes (AGENTS.md, READMEs). The `ft-` prefix can stay |
| Server start command | `filament_tracker.main:create_app` | Any script, service or Compose file that starts the server must change |
| Database and key files | `data/filament.db`, `data/settings.key` | **Breaks an install** if the default file names change: the server would start on an empty database and a new key. Keep the names, or move the files as part of the upgrade |
| Docker image and container | `ghcr.io/sirmeili/rollcall`, container and volumes `rollcall` (M9) | A later rename means a new image name, with the same volumes so no data is lost |
| Android app ID and Kotlin packages | `io.github.sirmeili.filamenttracker` | **Breaks updates**: Android treats it as a new app. Send the offline queue first, uninstall, install, pair again (the device token in the Keystore is lost) |
| Android Keystore alias | `filament-tracker-storage` | Lost with the uninstall anyway; rename with the app ID |
| Phone app name | **Done (2026-11-10)**: Capacitor `appName` and the launcher label "RollCall", was "Filament Tracker" | Safe |
| Write header | `X-Requested-With: filament-tracker` | **Breaks writes** if the server and web app disagree. The phone app carries its own copy of the web app, so change both together and reinstall the phone app |
| Session cookie | `ft_session` | Renaming signs everyone out once |
| Device token prefix | `ftd_` | **Breaks every paired scanner** if the server stops accepting `ftd_`. Keep it, or accept both prefixes |
| Browser storage keys | `ft-theme` and similar | Saved preferences reset once; harmless |
| Home Assistant device and entities | node ID `filament_tracker` (discovery topics, `unique_id`s, the availability topic), device "RollCall" (**Done 2026-11-10**: renamed from "Filament Tracker"; only the shown name changed, so entity IDs stay and nothing breaks) | New entities appear and the old ones go. The server clears retained messages only under its own node ID, so the rename must clear the old node's retained discovery messages once, or they stay in Home Assistant |
| Home Assistant events | `filament_tracker_spool_received`, `_opened`, `_emptied`, `filament_tracker_low_stock` | Automations listening for the old names stop firing; edit them and `docs/home-assistant/low-stock-automation.yaml` |
| MQTT client IDs, API title, logger names | `filament-tracker-<random>` | Safe |
| Scanner firmware | Not written yet | Use the final name from the start |

- **Code rename decisions** (owner, 2026-11-10; to be done later on its own branch, `feature/rename-rollcall`, not yet scheduled). The owner is the only user and everything is still in testing, so every name changes:
  - Python package `rollcall`; commands `rc-admin`, `rc-sim`, `rc-printer`, `rc-ha`, `rc-fakeprinter`; environment variables `RC_` instead of `FT_` (for example `RC_TOKEN`).
  - Database file `data/rollcall.db`. On start, when `rollcall.db` is missing and `filament.db` exists beside it, the server renames the old file, so the data carries over with no manual step. `settings.key` keeps its name.
  - Android app ID `io.github.sirmeili.rollcall` (accepted: send queued scans, uninstall, install, pair again).
  - Device token prefix `rcd_` (accepted: paired devices pair again).
  - Home Assistant node ID `rollcall` and events `rollcall_spool_received`, `rollcall_spool_opened`, `rollcall_spool_emptied`, `rollcall_low_stock`; the server clears the old node's retained discovery messages once (accepted: automations are edited).
  - Session cookie and write header renamed (accepted: everyone signs in again once), with the browser storage keys, Keystore alias, MQTT client IDs and logger names.

### Structure: one app, two modules

- One application, one database and one Docker image, with two modules: **Inventory** (everything built so far) and **Print Requests** (new). Print Requests uses Inventory; Inventory never imports Print Requests, checked by a test that reads each module's imports.
- What Print Requests needs from Inventory goes through Inventory's services: stock and available grams, holds on spools (see 2.5, where a hold names its holder only as an opaque reference), products and the catalog.
- Each module has its own route group under `/api/v1` and its own pages, so the request pages can be found, tested and documented on their own.

### Access from outside the home

- **The whole web app stays reachable from the internet**, as today, through the owner's HTTPS reverse proxy with personal accounts. Only scanning and saving scans stays on the home network (`/scans`, heartbeat, provisioning and bearer tokens, as today); away from home the phone app queues scans and sends them on its return.
- **Requester role**: see Users and roles. A Requester reaches only the request route group, the catalog and the stock summary, which the server enforces on every route, so it does not depend on what the proxy forwards.
- **Recommended exposure: a Cloudflare Tunnel** to the web app's hostname. It needs no open port on the home router and hides the home address, and the app's own accounts do the signing in. Cloudflare Access can be added in front as a second sign-in (for example a one-time code to an allowed email address) at the cost of signing in twice in a browser; the phone app passes it with a service token (see Phone scanner, Away from home). **Tailscale** is the alternative if both people are happy to install it: nothing is public at all, but every device that uses the app, including the brother's, must join the tailnet. Either way the tunnel forwards only the web app and `/api/v1`, never the API docs.

### Phase 2

#### 2.1 Filament catalog from the Open Filament Database

- **Summary**: a local copy of the Open Filament Database (OFDB) catalog, so requests and the shopping list can offer every Bambu color, not only those on the shelf.
- **Requirements**:
  - Download the bulk export from `api.openfilamentdatabase.org` (`json/all.json.gz`, or the SQLite `sqlite/filaments.db.xz`) on a schedule: a setting with off, daily (default) and weekly. Send `If-None-Match`/`If-Modified-Since` so an unchanged file is not downloaded again; OFDB rebuilds once a day.
  - Keep only the brands that are switched on, Bambu Lab by default; any brand can be switched on later.
  - Replace the catalog tables in one transaction. A failed or partial download keeps the last good copy. The catalog never writes to `product`, `spool`, `tag` or `event`.
  - The Settings page shows the last successful sync, the last attempt and its result, the dataset version (for example `v2026.11.07`), and a **Refresh now** button (Admin).
  - Catalog colors and owned products are separate. A product links to its catalog color by the tag's material and variant IDs through the color code table (2.2), and by brand, material and color name where the table has no row.
  - **Closest in-stock color**: each catalog color keeps its hex. Distance is CIEDE2000 in CIELAB (sRGB, D65), never raw RGB. It is a pure function with Sharma's published test pairs as unit tests, so no new dependency is needed. Multi-color variants (OFDB `color_hexes`) compare by their first color and are labelled as multi-color.
- **Data model**: `catalog_brand`, `catalog_filament` (material line, for example PLA Basic, with density and temperatures), `catalog_variant` (color: name, hex, extra hexes, discontinued), `catalog_size` (weight, refill or spool, article number, purchase links), all keyed by OFDB's UUIDs, with `moved_from` so links survive OFDB merges. `catalog_sync` (started_at, finished_at, result, dataset_version, etag). `product.catalog_variant_id` (nullable).
- **Risks and open questions**: OFDB is community-maintained, so a color can be missing or wrong; the color code table (2.2) can correct it locally. The data is MIT-licensed; attribution is shown on the Settings page.
- **Dependencies**: M9 settings in the app.
- **Found** (2026-11-07): OFDB data is on GitHub (`simplyprint/open-filament-database`), rebuilt daily into static JSON, NDJSON, SQLite and CSV at `api.openfilamentdatabase.org`, under the MIT license. Bambu Lab has 50 filament lines with 304 colors, every one with a hex.

#### 2.2 Bambu color codes and store links

- **Summary**: each Bambu color's 5-digit code (for example 10204, PLA Basic Hot Pink), tied to the tag's IDs, so the app can link straight to the store.
- **Requirements**:
  - A color code table, seeded at each catalog sync from two sources and editable by an Admin: OFDB's `article_number` on each size, and BambuStudio's `filaments_color_codes.json` (5-digit code, filament ID such as `GFA00`, a two-letter color code such as `R3`, hex and names in 12 languages).
  - The tag link: a tag's material ID is BambuStudio's filament ID (`GFA00`), and its variant ID is usually the filament ID without `GF`, a hyphen and the color code (`A00-R3`). Exceptions are stored as manual rows, which a sync never overwrites.
  - Store links: a store base URL setting, default `https://us.store.bambulab.com`, and the link `{base}/search?q={code}`. A shopping list item or a missing color shows **Find in store**.
- **Data model**: `color_code` (code, filament_id, color_code, tag_variant_id, catalog_variant_id, hex, name, source `ofdb`, `bambustudio` or `manual`, updated_by).
- **Risks and open questions**:
  - The store search page shows its results in the browser, so whether a code search finds the right product has to be checked by hand before this is built.
  - BambuStudio is AGPL-3.0. The app downloads the one data file at sync time rather than copying it into this repo; check that this is acceptable before shipping.
  - BambuStudio's file can change shape without notice; the sync must fail safely and keep the last good copy.
- **Dependencies**: 2.1.
- **Found** (2026-11-07):
  - OFDB **does** include the 5-digit codes, as `article_number` on sizes: 297 of the 304 Bambu colors have one. Missing examples: PLA Basic Green, PETG Basic Purple, ASA Aero White.
  - OFDB has no tag material or variant IDs, so the tag link has to come from elsewhere. Its purchase links for the Bambu store carry a `?variant=` number, but the store now redirects them to the product page without it, so the color isn't picked.
  - BambuStudio's `filaments_color_codes.json` has 342 entries and does map codes to filament IDs and color codes. Checked against the five products with tags in the owner's database: four match exactly (`G02-K0` PETG HF Black 33102, `B00-K0` ABS Black 40101, `B01-R0` ASA Red 45200, `G01-N0` PETG Translucent Brown 32800). PLA Basic Black's tag reads `A00-K00`, while BambuStudio lists `K0` (10101), so exceptions do happen.
  - BambuStudio's filament profiles (for example `Bambu PLA Basic @base.json`, `filament_id` `GFA00`) hold material properties: density, flow, volumetric speed and cost. They can be an optional second source for temperatures and density.
  - The store's `/en/search` path redirects to `/search`. The regional store addresses (`eu.`, `uk.`, `ca.`, `au.store.bambulab.com`) all redirected a US visitor to the US store, so the store picks the region from where the visitor is. That's why the base URL is a setting, with the US store as the default.

#### 2.3 Requester role and print requests

- **Summary**: the brother signs in, submits a request with a model and filament choices, and follows it; the owner reviews and runs it. This replaces the Google Form.
- **Requirements**:
  - A request has a title, notes, quantity, an optional needed-by date, and either an uploaded file (3MF or STL) or a MakerWorld link, or both.
  - Filament choice per request, or per part once 3.1 and 3.4 exist: an owned product, shown with its available grams and spools, or a catalog color, shown with its closest in-stock color. Choosing a catalog color the shelf lacks adds it to the shopping list as a request item (2.6).
  - A Requester sees only their own requests. Admins and Editors see all of them, with a count on the navigation like Review's.
  - Uploads: at most 100 MB a file, checked by content (a 3MF is a zip; an STL is binary or ASCII STL) rather than by extension, stored outside the web root under a random name, and never run or served back with an active content type.
  - MakerWorld links are stored and shown as links only (see Found).
- **Data model**: `print_request` (id, requester_id, title, notes, quantity, needed_by, makerworld_url, status, estimate_grams, estimate_seconds, estimate_source `3mf` or `admin`, created_at, updated_at), `request_file` (id, request_id, original_name, kind `3mf_sliced`, `3mf_project` or `stl`, size, sha256, stored_name, parsed_json), `request_part` (id, request_id, file_id, plate, object_name, estimate_grams, product_id or catalog_variant_id), `request_status` (history: from, to, by user or automatic, at, note).
- **Risks and open questions**: uploads from the internet are the largest new attack surface: size limits, content checks, zip-bomb limits (3.1), and security tests for each.
- **Found** (2026-11-07):
  - MakerWorld has no public API. Its `robots.txt` allows model pages for crawlers, but its terms of use could not be read, so whether automated download is allowed isn't confirmed.
  - Until it is, the app stores the link only and never fetches from MakerWorld. The requester downloads the 3MF themselves and uploads it.

#### 2.4 Request status pipeline

- **Summary**: one set of states from submission to pick-up, moved by people and, from Phase 3, by the printer.
- **States**: Submitted, Accepted, Waiting on Filament, Queued, Printing, Done, Picked Up; and Rejected, Cancelled, Failed.

| From | To | How |
| --- | --- | --- |
| Submitted | Accepted, Rejected | Admin (Rejected needs a reason) |
| Submitted, Accepted, Waiting on Filament, Queued | Cancelled | Requester (own request) or Admin |
| Accepted | Queued | Automatic, when holds (2.5) cover every filament |
| Accepted | Waiting on Filament | Automatic, when something can't be held; links to its shopping list items |
| Waiting on Filament | Queued | Automatic, when a matching spool is received and the holds then cover it; or Admin |
| Queued | Printing | Automatic (3.2) when the printer starts the job linked to the request; or Admin |
| Printing | Done, Failed | Automatic (3.2) on the printer's finish or failure; or Admin |
| Failed | Queued | Admin, **Reprint**: a new attempt that holds the filament again |
| Failed | Cancelled | Admin |
| Done | Picked Up | Admin or Requester |

- **Notifications to the requester**: email (an `email` settings group: SMTP host, port, user, password as a secret, sender) on Accepted, Rejected, Waiting on Filament, Printing, Done and Failed. Each Requester can turn them off. On Done the Admin can attach a photo of the print (JPEG or PNG, re-encoded on upload to strip metadata).
- **Notifications to the owner**: a new request, by email, and by push from Phase 3 (3.3).
- **Data model**: `print_request.status`, `request_status` (2.3), `request_photo` (request_id, stored_name, uploaded_by, at).
- **Dependencies**: 2.3; 2.5 for the automatic moves out of Accepted; 3.2 for the printer moves.

#### 2.5 Holding filament for accepted requests

- **Summary**: accepting a request holds its estimated grams on specific spools, so the same filament isn't promised twice.
- **Requirements**:
  - **Grams per spool**: sealed counts as the tag's net weight (the decoder already reads it), or the catalog size's weight if there's no tag. Open counts as the net weight times the AMS remaining %, if the printer has reported one; otherwise its grams are unknown and the Admin enters a figure.
  - **Available** is grams minus active holds. It is shown on Inventory, Spool detail and in requests.
  - **Placing holds**: on Accepted, open spools are held first, then sealed ones, and the Admin can change which spools. What can't be held sends the request to Waiting on Filament.
  - **Releasing holds**: holds are released on Cancelled, Rejected and Failed (a reprint holds again).
  - **Reconciling**: on Done, the holds are replaced by the measured use (3.2). With no printer measurement, the estimate is taken as used.
- **Data model**: `spool_hold` (id, spool_id, grams, holder_type, holder_id, created_at, released_at, release_reason). This is Inventory's table, and it names its holder only by type and ID, so Inventory never depends on Print Requests. `spool.used_grams`, adjusted by usage events.
- **Risks**: AMS remaining % is coarse and is missing for spools the AMS hasn't seen. Available grams are an estimate, so they are shown with "about".
- **Dependencies**: 2.3, 2.4.

#### 2.6 Low stock and the shopping list

- **Summary**: extend the low-stock rules that exist, rather than adding new ones, and add a shopping list.
- **Already built**:
  - Each product has a low-stock threshold, and it is low when its sealed count is at or below the threshold (0 turns this off). "Always keep 2 Black PLA Basic" is already this rule.
  - Low stock feeds the Home Assistant Low filament sensor and the `low_stock` event, and the example automation adds the product to Home Assistant's shopping list.
- **Extensions**:
  - **A rule for a color not yet owned**: create a provisional product from a catalog color, with its threshold. Provisional products exist already for manual entry, so no new rule table is needed.
  - **Shopping list**, in the app. Items come from three sources:
    - Low stock, automatically: the quantity needed to stop being low, `threshold - sealed + 1`.
    - Catalog colors chosen in requests.
    - Items added by hand.
  - **Grouping**: items are grouped by material line (PLA Basic, PETG HF and so on), with the line's total, so bulk deals are easy to reach.
  - **Item actions**: Find in store (2.2), Ordered and Dismiss. Receiving a spool of that product closes its item automatically.
- **Data model**: `shopping_item` (id, product_id or catalog_variant_id, quantity, source `low_stock`, `request` or `manual`, request_id, status `open`, `ordered`, `received` or `dismissed`, created_by, created_at, updated_at).
- **Dependencies**: 2.1 and 2.2 for catalog colors and store links.

### Phase 3

#### 3.1 Reading 3MF files

- **Summary**: take what a 3MF already says about plates, parts, colors, grams and time, so the Admin doesn't have to estimate by hand.
- **What's in each kind of file**:
  - **Sliced 3MF** (Bambu Studio "Export plate sliced file", `.gcode.3mf`): `Metadata/slice_info.config` has each plate's predicted time and weight, and a `<filament>` entry for each slot used, with type, color, `used_m` and `used_g`. Its `id` counts from 1, while the arrays in `project_settings.config` count from 0.
  - **Project 3MF** (saved, not sliced): `Metadata/model_settings.config` has the objects, their parts, their plates and the filament assigned to each part, and `Metadata/project_settings.config` has each filament slot's type and color. There are no gram or time estimates.
  - **Plain 3MF** from other software: only objects, and maybe colors.
  - **STL**: one part and nothing else.
- **Requirements**:
  - Read what's there and show it on the request.
  - **Fallback**: anything missing is left for the Admin to enter (grams per filament, time). An STL always gets the Admin's estimate. A file that can't be read is kept and flagged, never refused, so nothing the requester sent is lost.
  - **Safe parsing**:
    - At most 2,000 zip entries and 500 MB uncompressed (zip-bomb guard).
    - XML read with entity expansion off (`defusedxml`, vetted when added).
    - No path from inside the zip is used as a file name.
    - The parser runs with a time limit.
- **Data model**: `request_file.parsed_json` (plates, objects, parts, filaments with grams, seconds, and the slicer and its version), `request_part` rows filled from it.
- **Risks**:
  - Bambu's 3MF extensions are not documented. The fields above come from community parsers, so tests use real files from the owner's own prints, kept out of the repo like tag dumps unless they're the owner's own models.
  - OrcaSlicer and PrusaSlicer write different metadata, so only what the parser recognises is used.
- **Found** (2026-11-07): as above, from community parsers (`lib3mf-core`, `libprintcalc`) and write-ups. `plate_N.json` files exist in sliced files, but their fields weren't confirmed.

#### 3.2 Print jobs from the printer

- **Summary**: follow print status, progress and the current job, and record what each job used, using the printer link that already exists rather than adding a second connection, and without Home Assistant.
- **Already built** (M5):
  - One TLS MQTT connection per printer, with a pinned certificate.
  - The report merged into a full view, giving the AMS trays' material, color, remaining % and tray ID.
  - Read-only apart from `pushall`.
  - The report also carries the job fields, which are received today but not used.
- **Requirements**:
  - **Reading jobs**: read the job state (`gcode_state`: idle, preparing, running, paused, finished, failed), progress (`mc_percent`), time left (`mc_remaining_time`), layer (`layer_num` of `total_layer_num`), the job name (`subtask_name`) and the active tray (`tray_now`) from the same reports. Check each field against `ft-printer check` captures before building on it.
  - **Recording jobs**: each job is a `print_job` row from start to end.
  - **Linking a job to a request**: the Admin marks a queued request **Next to print**, and the next job that starts is linked to it. A job that starts with nothing marked can be linked afterwards, or left as the owner's own print.
  - **Usage**: grams per tray come from the 3MF estimate for the linked request (3.1), split across the trays the job used, and checked against each tray's remaining % before and after. The printer reports no grams. A large mismatch is flagged in Review, and the Admin can correct the figure.
  - **Moves**: the job's start, finish and failure move the request (2.4) and settle its holds (2.5).
  - **Pages**: the printer page shows the current job and progress.
  - **Read-only stays**: the app never starts, pauses or stops prints. Doing that would need Developer Mode and is not planned.
- **Data model**: `print_job` (id, printer_id, started_at, ended_at, result, subtask_name, request_id, usage_json: grams per spool, with the source `estimate`, `ams` or `admin`). Usage is also recorded as a `used` event on each spool, so the spool's history shows it and it can be undone.
- **Risks**:
  - Since January 2025, Bambu firmware authenticates control commands. Bambu's wiki says Developer Mode turns that off and accepts every command, without support from Bambu.
  - Read-only reports work on the owner's P1S today, without Developer Mode (M5). A later firmware could restrict LAN reports too, which would stop this item and AMS detection alike. Watch the release notes before each firmware update.
  - P1 printers allow few MQTT connections; the MQTT proxy route already covers that.
- **Dependencies**: M5 (built), 3.1, 2.4, 2.5.

#### 3.3 Push notifications to the phone app

- **Summary**: low stock, and new requests for the owner, arrive as phone notifications from the existing Android app.
- **Options compared**:
  - **Firebase Cloud Messaging**: the most reliable on stock Android, but it needs a Google project and a `google-services.json` in the app, and every message goes through Google. That cuts against the no-cloud goal.
  - **A persistent connection from the app**: no third party, but Android's battery limits (Doze) stop it in the background unless it runs as a foreground service with a permanent notification.
  - **UnifiedPush with ntfy**: self-hostable, no Google, and messages encrypted end to end (Web Push encryption). The phone needs a distributor app, ntfy, installed.
- **Recommendation: UnifiedPush, with a self-hosted ntfy server** added to the Compose file, reachable through the same tunnel as the web app, since the phone is often away from home.
  - **Before the app work**: the owner can subscribe the ntfy app to a private topic, with no app changes.
- **What the Android app adds**:
  - The UnifiedPush connector library (vetted under the dependency rules).
  - Android 13's notification permission.
  - Registering its endpoint with the server and removing it on unpairing.
  - A notification that opens the right page.
- **Server**: sends Web Push-encrypted messages to each registered endpoint. Settings say which events notify whom.
- **Data model**: `push_endpoint` (id, user_id, device_id, endpoint, public keys, created_at, last_ok_at, failures), dropped after repeated failures.
- **Dependencies**: M8 (built), M9.

#### 3.4 Picking colors on the model

- **Summary**: on a multi-part 3MF, the requester gives each part a filament by clicking it on the model, using the owner's own viewer (`sirmeili/3d-mockup-viewer`) rather than a new one.
- **What the viewer already does** (v0.3.0):
  - Loads STL, 3MF and GLB in the browser.
  - Splits a 3MF into one part per build item, following Bambu Studio's and PrusaSlicer's multi-file objects and component transforms. Part names come from the object names.
  - Gives each part a material or a `#rrggbb` color, and highlights a part when its row in the Parts panel is hovered.
  - An embedding API: an iframe driven by `postMessage`, with `load`, `setFinish`, Arrange, and a `change` event that returns the edited manifest.
  - Ignores the 3MF's own colors and materials.
- **To add to the viewer**:
  - **Click to pick** a part on the 3D view, with a `select` event to the host page.
  - **An API call to set one part's color** (`setPartColor(id, hex)`), and one to read the part list with ids and names.
  - **Splitting a Bambu object's parts (volumes)** into separate parts. Today a build item becomes one part, and a multi-color Bambu object is often one object with several parts; check this with a real file.
  - **Optionally, reading the filament assigned to each part** from `model_settings.config`, to start with the slicer's choices.
  - **Limit**: painted (per-face) color in a 3MF can't map to parts, so that case uses the list fallback.
- **Requirements**:
  - **Slot check**: the number of distinct filaments is checked against the printer's AMS slots (4 per AMS, 1 per AMS HT, from `printer_slot`). Anything over that is flagged as needing manual swaps.
  - **Fallback**: a simple per-part list is used when parts can't be told apart, or the viewer can't load the file.
- **Dependencies**: 3.1, 2.3, and a viewer release with the additions above.

#### 3.5 API and MCP server

- **Summary**: the documented REST API covers the new areas, and an MCP server on top lets Claude Code and other agents ask and act.
- **Requirements**:
  - **REST**: new route groups for the catalog, requests, holds, the shopping list and printer jobs, in the OpenAPI docs (LAN only, as today).
  - **MCP**: Streamable HTTP at `/mcp` in the same app, authenticated with a machine token (M9), so from the home network only, like every bearer token. This is the first app in the owner's set to have one, so it sets the pattern for the rest.
  - **Scopes**: each machine token has a scope, `read` by default. Write tools are listed only to a token with `write`, and every write is recorded in Activity under the token's name.
  - **Tools**, chosen so the examples work:
    - `stock_lookup`: by product, material or color, with available grams.
    - `catalog_search`.
    - `check_request`: "do we have enough white PETG for this request?" compares the request's estimate with available grams.
    - `request_list` and `request_get`.
    - `shopping_list`.
    - `printer_status`.
    - Write: `shopping_list_add` ("add 2 rolls of Black PLA Basic"), `request_set_status` and `hold_adjust`.
  - **Built on the REST services**, so the MCP server has no rules of its own.
- **Dependencies**: M9 machine tokens; the official MCP Python SDK, vetted when added.

### Later

#### L.1 Ask RollCall (on-demand agent)

- **Summary**: an optional button that asks an LLM agent to reason over the app's data, through the same tools as 3.5.
- **Examples**:
  - The best in-stock filament for a request.
  - A feasibility check on a 3MF: size against the build plate, materials, AMS slots and supports.
  - A shopping list draft.
  - A usage summary.
- **Requirements**:
  - **Provider**: behind an interface, with the Anthropic API (and the Claude Agent SDK) first and room for a local model.
  - **Settings**: an `assistant` settings group, with the API key as a secret and the model as a setting rather than written into the code. The feature is off when no key is set.
  - **How it runs**: started from a button on a request, the shopping list or the dashboard. It runs in the background, and its result is saved on the item as a note.
  - **The agent only proposes**: it gets read tools only. Changes come back as proposed actions that a person approves, and each approved action runs through the API as that person.
  - **Logging**: every run is logged with its prompt, the tools called and their results, tokens and cost.
  - **Data sent to the provider**: only what the tools return. Uploaded files are not sent, only what 3.1 read from them. The Settings page says so.
- **Data model**: `agent_run` (id, trigger, subject_type, subject_id, provider, model, prompt, tool_calls_json, result, proposed_json, input_tokens, output_tokens, cost, started_by, started_at, finished_at, status).
- **Dependencies**: 3.5.

#### L.2 Spool lifecycle stats

- **Summary**: from scan events and printer usage, show:
  - grams used per month;
  - use by material and color;
  - how long spools stay open, which helps with drying;
  - cost per print;
  - each person's use, with a running cost-split tally for the co-owners.
- **Requirements**:
  - **Spool prices**: a price per spool, entered on receiving, or a product default. Neither OFDB nor the tag has prices, and BambuStudio's `filament_cost` is only a default.
  - **Whose use**: a job linked to a request counts as the requester's, and any other job as the owner's.
- **Data model**: `product.default_price`, a `price` field on `received` events, and views over `print_job` and `event`.
- **Dependencies**: 3.2.

### Verification findings

| Claim | Finding (2026-11-07) |
| --- | --- |
| Low-stock rules exist | **Yes**: a per-product threshold, low when sealed is at or below it, with Home Assistant entities and events and an example automation. Phase 2 extends it (2.5) instead of adding a second rule system |
| A printer connection exists | **Yes**: direct, read-only TLS MQTT with a pinned certificate, an MQTT proxy option and a fake printer (M5). Phase 3 builds on it (3.2) |
| A REST API exists | **Yes**: `/api/v1` with OpenAPI docs on the LAN. Machine tokens with roles are planned in M9; MCP (3.5) uses them |
| OFDB has Bambu's 5-digit codes | **Yes**: `article_number` on sizes, for 297 of 304 Bambu colors. It has no tag IDs |
| OFDB has a hex per color | **Yes**, for all 304 Bambu colors, plus `color_hexes` for multi-color filaments |
| BambuStudio maps color codes | **Yes**: `resources/profiles/BBL/filament/filaments_color_codes.json` (342 entries). It matches the tag IDs of 4 of the owner's 5 tagged products; PLA Basic Black (`A00-K00`) is an exception |
| BambuStudio profiles give material properties | **Yes**: the `@base` profiles have `filament_id`, density, flow, speed and cost |
| Store links by code | `https://us.store.bambulab.com/search?q=<code>` is the search URL. **Not confirmed**: whether a code finds the product, since results show only in the browser. OFDB's links to a store variant no longer pick the color |
| The store is region-aware | **Yes**: the regional addresses redirect by the visitor's location. The base URL is a setting, US by default |
| Sliced 3MF metadata | **Yes**: per-plate time and weight, and per-filament `used_g`, in `slice_info.config`. Unsliced project files have parts and filament assignments but no estimates. The format is undocumented by Bambu |
| MakerWorld import | **Not possible to confirm**: there is no public API and the terms couldn't be read. The link is stored only |
| Bambu LAN access | Read-only reports work on the owner's P1S today. Control needs Developer Mode, which isn't planned. A future firmware change could limit LAN reports (see 3.2) |
| The 3D viewer can pick parts | **Not yet**: it has per-part colors, an embedding API and hover-highlight from the list, but no clicking on the model and no per-part color call. See 3.4 |
| Push options | UnifiedPush with ntfy is recommended over FCM (Google dependency) and a persistent connection (Android battery limits) |

## Open questions

- [ ] Does a tag read through the sealed shipping box with the PN532, and from which side? If not, New needs another trigger (box barcode, or scanning at first opening). A Pixel 9 Pro XL reads tags through sealed refill boxes from either side, but a phone antenna is not a PN532. Tags in TPU's foil bag cannot be read; see Manual entry.
- [x] The AMS tray UUID equals the tag's tray UID (checked on a P1S with `ft-printer check` against a scanned tag).
- [ ] How does the AMS report a non-Bambu spool? Expected: no tray UUID (all zeros) and a remaining % of -1. Check when one is loaded.
- [x] Buttons on the CYD prototype: resistor ladder on GPIO35. The PCF8574 expander stays as the fallback.
- [x] Printer data source: direct MQTT from the server, which also works through an MQTT proxy if the printer's connection limit is hit.
- [x] Refill packs carry Bambu tags that read through the box. A refill has its own tray UID, so it is tracked as a new spool.
- [ ] Project name. Working name RollCall (2026-11-09, replacing Spoolhouse), not final; the repo is already `sirmeili/rollcall`, and the rename of the code waits until the name is settled.
