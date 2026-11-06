# Filament Tracker — Spec

Oct 31, 2026 · @Frank

## Overview

A self-hosted system that tracks every Bambu Lab filament spool from delivery to empty, using the RFID tags already on the spools. You tap a spool on a small touchscreen scanner, or on an Android phone running the companion app; it shows what the spool is and asks whether it is new, just opened or empty. A central server keeps the inventory, feeds Home Assistant and serves a web app that a few people can use, some only to view.

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
- Slicer integration or automatic filament usage from G-code.

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
- A spool first seen through the AMS is assigned to an existing product if its AMS data matches exactly one: the same material ID (the AMS `tray_info_idx`) and color. If it matches none or several, the server creates a provisional product from the AMS filament type and color. Either way the spool is flagged for review. A later scan of one of its tags wins: the spool moves to the tag's product, and a provisional product left with no spools is removed.
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
- **The full web app**: every page, after a normal user sign-in. Scanning uses the device token, not the user's session.
- Scan and Pairing work without a user sign-in, and Scan works without the server (offline). The app opens on Scan once paired, and on Pairing until then. In a browser these two screens only say they belong to the app.
- Like the scanner's "Last scan", Scan keeps the last scan with an Undo: it reverts the event, or takes it out of the queue if it has not been sent yet. Info shows the AMS remaining % and links to the spool's page.

**Device behavior**

- Scans and undo of its own events use the device token, exactly as the scanner does. A heartbeat is sent every 5 minutes while the app is open.
- Offline, as on the scanner: if the lookup fails, the product, type and color are decoded on the phone from the raw tag, New, Opened and Empty are offered, and chosen actions are queued (at least 50) and retried with backoff. The `event_id` makes retries idempotent. The Scan screen shows the queue size.

**Pairing**

- Registering a device or rotating its token on the Devices page also shows a QR code, once, holding the server URL, the token and the device ID (scans must name their device). The URL defaults to the address the admin is using and can be changed before the code is shown. The code holds JSON, `{"v": 1, "url": "...", "token": "...", "device_id": "..."}`, so the format can change later.
- The app scans the QR code with the camera; typing the URL and token is the fallback.
- The token and the key-derivation constant are stored encrypted with the Android Keystore. The constant comes from `GET /devices/provisioning` after pairing and is never bundled in the app. The app opts out of Android backup, because the Keystore key cannot be restored on another phone; a restored or damaged value reads as missing and the phone pairs again.

**Network**

- The app allows plain HTTP for LAN addresses, like the scanner, and HTTPS everywhere. A LAN address is a private IPv4 or IPv6 address, `localhost`, a name without dots, or a name ending in `.local`, `.lan` or `.home.arpa`; pairing refuses any other `http://` address.
- The session cookie is `Secure`, so signing in over a plain `http://` address works only with `COOKIE_SECURE=false`. Pairing with the HTTPS address of the reverse proxy is recommended: scanning still works on the LAN, because the proxy forwards the phone's LAN address.

## Server: data model

The server is event-sourced: every scan, AMS observation and UI edit is an immutable event, and each spool's current state is derived from its events. This makes undo and audit trivial.

**Stack**: Python 3.12, FastAPI, SQLAlchemy with SQLite (WAL mode), Alembic migrations, a SvelteKit web app (TypeScript, built as static files and served by FastAPI), one Docker image.

**Tables**

| Table | Key fields | Purpose |
| --- | --- | --- |
| `product` | id, material\_id, variant\_id, filament\_type, color\_rgba, display\_name, low\_stock\_threshold, nearly\_out\_pct, provisional | One row per filament product (for example Black PLA Basic); created automatically from the first decoded tag; display name editable. `nearly_out_pct` (default 15) is the AMS remaining % at or below which an open spool is shown as nearly out. Provisional products (from the AMS or manual entry) have no material or variant ID until a tag is scanned |
| `spool` | id, tray\_uid (unique, null for a manual placeholder), product\_id, state, received\_at, opened\_at, emptied\_at, remaining\_pct, location, notes, likely\_empty\_dismissed\_at | One physical spool; state and timestamps derived from events. State is null (Unknown) when every event that set it has been undone. `likely_empty_dismissed_at` hides its "Likely empty" suggestion |
| `tag` | uid (unique), spool\_id, raw\_blocks, decoded\_json, first\_seen\_at, dismissed\_at | Each spool has up to two tags; raw dump kept for re-decoding. `dismissed_at` hides an `unidentified` tag from Review |
| `event` | id (UUID from device or server), spool\_id, type, source, device\_id, user\_id, occurred\_at, flagged, reviewed\_at, reviewed\_by, payload\_json, reverted\_by | Append-only log; undo writes a new `revert` event. `user_id` records who acted in the web app |
| `device` | id, name, token\_hash, revoked\_at, last\_seen\_at, fw\_version, queue\_length | Registered scanners; firmware version and offline queue length come from the last heartbeat |
| `user` | id, username (unique, case-insensitive), password\_hash, role, disabled\_at, last\_login\_at | Web app accounts; see Users and roles |
| `session` | id, token\_hash, user\_id, expires\_at, last\_seen\_at | Signed-in browsers; only a hash of the cookie value is stored |
| `printer` | id, name, serial, host, port, cert\_sha256, last\_report\_at | Printers watched over MQTT, synced from `PRINTERS` at startup. `cert_sha256` is the pinned TLS certificate fingerprint |
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

A versioned REST API under `/api/v1`, documented by FastAPI's generated OpenAPI page (LAN only). Scanners authenticate with a device token and Home Assistant with the admin token, both bearer tokens accepted only from the LAN. The web app uses a session cookie, and each route requires a minimum role (see Users and roles).

| Method | Path | Caller | Purpose |
| --- | --- | --- | --- |
| POST | `/auth/login`, `/auth/logout` | Web app | Sign in with username and password; sign out |
| GET | `/auth/me` | Web app | Current user and role |
| POST | `/auth/password` | Viewer | Change own password; ends the user's other sessions |
| POST | `/scans` | Scanner | Submit a scan event; a lookup returns spool, product, state, allowed and suggested actions; an action returns the new state and a `feedback` code for the screen |
| POST | `/devices/heartbeat` | Scanner | Online status, firmware version, queue length |
| GET | `/devices/provisioning` | Scanner | Returns the key-derivation constant to an authenticated device (scanner firmware and the phone app) |
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
| GET | `/health` | Docker, HA | Liveness and dependency status |

**Scan response feedback codes**: `ok`, `ok_created` (implicit receive), `already_in_state`, `flagged` (out of order), `unreadable`, `error`. The device maps each to a screen message and sound.

**Idempotency**: a repeated `event_id` returns the original result without writing a second event.

## Users and roles

The web app has personal accounts, so a few people can use it from anywhere, some only to look.

| Role | Can |
| --- | --- |
| Viewer | See every page: inventory, spools, products, review, activity |
| Editor | Also record actions, undo, edit spools and products, add spools by hand, resolve review items |
| Admin | Also manage users and scanners |

- Accounts are created by an admin; there is no sign-up. The first admin is created from the command line (`ft-admin create-user`), so there is never a default account. `ft-admin reset-password` recovers an account when no admin can sign in.
- Passwords are at least 12 characters and stored as Argon2id hashes. Users can change their own; an admin can reset one or disable an account.
- Signing in sets a session cookie (HttpOnly, Secure, SameSite=Strict) valid for `SESSION_DAYS`. Sessions end on sign-out, on a password change (other sessions), or when the account is disabled.
- Events recorded in the web app store who made them, and the Activity page shows it.

## Server: web UI

A small, mobile-friendly web app for checking stock and fixing mistakes; day-to-day input comes from the scanner. It is a SvelteKit single-page app built to static files, so production needs no Node.js. Controls a user's role does not allow are hidden, and the API enforces the same rules. The look follows the mockups in `docs/mockups/web/`. A header control chooses the theme: Light, Dark or System (follow the device), remembered in the browser.

| Page | Shows | Actions |
| --- | --- | --- |
| Inventory | One card per product: color swatch, name, sealed / open / used-up counts, low-stock badge (sealed count at or below the product's threshold; 0 turns it off), and a remaining % bar for each open spool, marked nearly out at or below the product's nearly-out %. A summary counts open spools that are nearly out | Filter by type; sort by low stock; switch between cards and a list |
| Spools | Table of spools with state, product, location (and AMS slot while loaded), remaining %, dates | Filter by state and type, search, bulk change location, add a spool by hand |
| Spool detail | Tag data, AMS remaining % and grams left (remaining % of the tag's spool weight), the AMS slot while loaded (for example "AMS 1, slot 2 on P1S"), event timeline | Manual action, undo, edit notes and location |
| Products | Decoded product IDs and colors | Set display name, low-stock threshold and nearly-out % |
| Review | Flagged events, `unidentified` tags, "likely empty" suggestions | Flagged event: Accept (it was right), Undo (revert it) or Open spool (fix by hand). Unidentified tag: dismiss. Likely empty: mark used up or dismiss. After an Accept or a dismiss, Bring back returns the item to Review |
| Devices | Scanners (including phones) and printers with online status, firmware, queue; each printer shows its AMS slots and the spool in each, and warns when its certificate does not match the pin | Register device (token shown once, with a QR code for the phone app), rotate token, revoke; forget a printer's certificate pin |
| Users | Accounts and roles (Admin only), with a short description of what each role can do | Create, change role, reset password, disable |
| Account | The signed-in user | Change password (with a meter showing progress to the 12-character minimum), sign out |
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
- **MQTT proxies**: `PRINTERS` may point at an MQTT proxy instead of the printer, to stay under the printer's connection limit. A proxy such as `bambu-mqtt-proxy` speaks the same protocol (TLS on 8883 with its own certificate, user `bblp`, the access code, the same topics, and it forwards `pushall`), so it needs no special support: set its host and port, and use the alias as the serial if the proxy renames the printer. The pin is then the proxy's certificate. Any proxy is a separate project, not part of this system.
- A **fake printer** replays recorded or documentation-based report messages over TLS, so this integration can be tested without a printer.

**Home Assistant**

- Publish entities through MQTT discovery to the existing broker, under one device "Filament Tracker":
  - a sensor per product: sealed count (attributes: open count, color, display name);
  - a binary sensor per product for low stock;
  - a sensor for total sealed spools and one for spools in review.
- Fire HA events through the REST API for automations: `filament_tracker_spool_received`, `_opened`, `_emptied`, `_low_stock`.
- Example automation the user can build: on low stock, add the product to the shopping list and notify a phone.
- Any automations or scripts created for this project get the `Claude` label.

**Spoolman (optional, later)**

- One-way sync of spools and states into Spoolman, using the tray UID as the lot number. Off by default.

## Security and deployment

**Deployment**

- One Docker image, run with Docker Compose; SQLite database on a mounted volume.
- The web app may be exposed to the internet, but only through an HTTPS reverse proxy the owner runs (for example Caddy, Nginx Proxy Manager, Traefik or a Cloudflare Tunnel). The app itself speaks plain HTTP to the proxy and trusts forwarded client addresses only from `FORWARDED_ALLOW_IPS`.
- Scanner routes, bearer tokens (device and admin) and the API docs are accepted only from `TRUSTED_NETWORKS`, so they stay on the LAN even if the proxy forwards everything. The proxy should forward only the web app and `/api/v1` anyway.
- Nightly SQLite backup (online backup API) to a second volume, 14 kept.

**Configuration** (environment variables or a `.env` file, never committed)

| Setting | Example | Purpose |
| --- | --- | --- |
| `ADMIN_TOKEN` | random 32 bytes | Machine access for Home Assistant and scripts, from the LAN only |
| `BAMBU_KDF_SALT` | hex string | Key-derivation constant, served to provisioned devices |
| `PRINTERS` | `[{"name": "P1S", "host": "192.168.1.40", "serial": "01P00A...", "access_code": "..."}]` | Printers to watch over MQTT, as a JSON list; each entry may also set `port` (default 8883). `host` and `port` may be an MQTT proxy's |
| `MQTT_URL`, `MQTT_USER`, `MQTT_PASSWORD` | HA broker | Discovery and state publishing |
| `HA_URL`, `HA_TOKEN` | long-lived token | Firing HA events |
| `TZ` | `America/New_York` | Timestamps in the UI |
| `TRUSTED_NETWORKS` | `192.168.0.0/16,10.0.0.0/8` | LAN ranges allowed to use bearer tokens, scanner routes and API docs; defaults to the private ranges |
| `FORWARDED_ALLOW_IPS` | `192.168.1.5` | Address of the reverse proxy whose `X-Forwarded-For` is trusted |
| `SESSION_DAYS` | `30` | How long a web sign-in lasts |
| `COOKIE_SECURE` | `true` | Set `false` only to sign in over plain HTTP on the LAN during development; production is HTTPS |
| `WEB_DIR` | `/app/web` | The built web app; defaults to `web/build` in a source checkout |

**Security requirements**

- Every endpoint except `/health`, `/auth/login` and `/auth/logout` (which only ends the caller's own session, if any) requires authentication, and each enforces a minimum role.
- Sign-in attempts are throttled per username and per client address (HTTP 429), and failures give the same message whether the username exists or not.
- State-changing requests made with a session cookie must carry the `X-Requested-With: filament-tracker` header, which other sites cannot send, in addition to SameSite cookies.
- Responses carry a Content Security Policy, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` and a strict referrer policy.
- Device tokens are stored hashed, revocable, and scoped to `/scans`, `/devices/heartbeat`, `/devices/provisioning` and `/events/{id}/revert` for events from that same device.
- Input validation on all payloads (Pydantic); block arrays capped in size.
- No tag UIDs or derived keys in logs above debug level, in line with the RFID guide's request not to publish UID/key pairs.
- The printer access code, HA token and `BAMBU_KDF_SALT` never appear in logs, and a rejected setting's error message does not repeat its value. The salt is returned only by `/devices/provisioning`, to a device token from the LAN.
- The printer access code and HA token never leave the server or appear in API responses or logs. The access code is sent only to a printer (or proxy) whose certificate matches the pin.

## Testing

The server is fully testable without hardware. Firmware logic is unit tested on a PC, and hardware behavior gets a short manual checklist.

| Layer | What is tested | How |
| --- | --- | --- |
| Decoder | Every field; two rolls of the same product yield the same product key | pytest against generated tags in CI, plus own spools and the public Bambu RFID library locally |
| State machine | Every transition in the table, out-of-order flags, undo | pytest, property tests for event replay |
| API | Auth on every route, idempotent scans, validation errors | pytest with FastAPI TestClient |
| Security | Unauthenticated access refused, role checked on every route, revoked tokens and ended sessions refused, sign-in throttling, bearer tokens refused from outside the LAN, CSRF header, security headers, oversized payloads rejected | pytest security suite, run in CI |
| Web app | Components, API client, role-based visibility | Vitest with Testing Library; 90% coverage; `svelte-check` and `npm audit` in CI |
| Web end to end | Sign in as each role, inventory, record and undo an action, review | Playwright against the real server with a database seeded by the scan simulator |
| Phone app | Scan flow, offline queue, on-phone decode, pairing | Vitest; 90% coverage |
| Phone NFC plugin | Key derivation (matching the server), block assembly, trailer stripping, encrypted storage | Kotlin unit tests with a fake tag; 90% line coverage (JaCoCo), excluding the Android glue that needs a phone: `FilamentTrackerPlugin` (NFC reader mode, camera, Capacitor calls), `AndroidMifare`, `KeystoreKey`, `PrefsValues` and `MainActivity` |
| Phone on hardware | Reading on a real phone, MIFARE Classic detection, QR pairing, offline queue, sign-in | Manual checklist per release |
| AMS ingest | Report messages produce the right events | Fake printer replaying recorded or documentation-based messages, including a report captured from a P1S with its identifiers replaced |
| Printer on hardware | Connection and pin, every AMS and AMS HT slot, tray UID matching a scanned tag, automatic Opened, remaining % | `ft-printer check` and a manual checklist, before a release that changes the printer link |
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
6. **M6 Home Assistant**: MQTT discovery entities, events, low-stock automation.
7. **M3a Firmware without hardware**: scan flow, offline queue and dedupe logic with PC tests, screen simulator.
8. **M0b Prove reading, PN532**: repeat the read tests on the bench rig and measure reading through the 1 mm lid and shipping box.
9. **M3b Firmware on hardware**: breadboard build, real drivers, provisioning, OTA.
10. **M4 Enclosure**: printed case, button labels, antenna placement, final wiring.
11. **M7 Later**: see Future enhancements.

## Future enhancements

- **Custom PCB scanner (v2)**: replaces the CYD prototype once the screen and menu flow are settled. ESP32-S3 module, PN532 and a tuned antenna on board, SPI touch TFT, three dedicated button inputs (no resistor ladder), front-facing RGB LED, buzzer, and USB-C power with an optional PoE variant, following the Harmony Hub replacement PCB work.
- **Load-cell scale**: weigh a spool for remaining grams when it is not in the AMS.
- **Spoolman sync**: one-way export, as described under Integrations.
- **Non-Bambu filament**: NTAG stickers in an open format, or QR labels printed by the server.
- **Second scanner by the printer**: same firmware, its own device token.

## Open questions

- [ ] Does a tag read through the sealed shipping box with the PN532, and from which side? If not, New needs another trigger (box barcode, or scanning at first opening). A Pixel 9 Pro XL reads tags through sealed refill boxes from either side, but a phone antenna is not a PN532. Tags in TPU's foil bag cannot be read; see Manual entry.
- [x] The AMS tray UUID equals the tag's tray UID (checked on a P1S with `ft-printer check` against a scanned tag).
- [ ] How does the AMS report a non-Bambu spool? Expected: no tray UUID (all zeros) and a remaining % of -1. Check when one is loaded.
- [x] Buttons on the CYD prototype: resistor ladder on GPIO35. The PCF8574 expander stays as the fallback.
- [x] Printer data source: direct MQTT from the server, which also works through an MQTT proxy if the printer's connection limit is hit.
- [x] Refill packs carry Bambu tags that read through the box. A refill has its own tray UID, so it is tracked as a new spool.
- [ ] Project and repo name.
