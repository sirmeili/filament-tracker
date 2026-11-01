# Filament Tracker — Spec

Oct 31, 2026 · @Frank

## Overview

A self-hosted system that tracks every Bambu Lab filament spool from delivery to empty, using the RFID tags already on the spools. You tap a spool on a small touchscreen scanner; it shows what the spool is and asks whether it is new, just opened or empty. A central server keeps the inventory and feeds Home Assistant.

**Goals**

- Know at a glance how many sealed and open spools exist for each filament (for example: Black PLA Basic, 3 sealed, 1 open).
- Record each spool's lifecycle with one tap and one confirm: New, Opened, Empty.
- Identify spools automatically from their Bambu RFID tags, with no manual typing of type or color.
- Use the P1S/AMS telemetry to fill in what the printer already knows (spool first loaded, remaining %).
- Surface low-stock alerts and inventory sensors in Home Assistant.
- Run fully on the LAN in Docker, with no Bambu cloud dependency.

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

iPhones cannot read MIFARE Classic; all readers in this project are PN532-class or PC/SC devices.

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

**Automatic detection from the AMS**

- The first time the P1S/AMS reports a tray UID the server has not seen opened, the spool moves to `open` with source `ams`. This covers spools opened and loaded without a scan.
- A spool first seen through the AMS is assigned to an existing product if its AMS data matches exactly one. If it matches none or several, the server creates a provisional product. Either way the spool is flagged for review. A later scan of one of its tags wins: the spool moves to the tag's product, and a provisional product left with no spools is removed.
- The AMS remaining % is stored on the spool and shown in the UI.
- When the AMS reports 0% remaining, the server raises a "Likely empty" suggestion; it does not mark the spool empty on its own.

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
- Bill of materials target: under $30 per unit, excluding the printed case.

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
- Heartbeat every 5 minutes so the server can show online/offline.

**Configuration**

- First boot opens a Wi-Fi setup portal (Wi-Fi, server URL, device token).
- The key-derivation constant is entered at provisioning or fetched once from `GET /devices/provisioning` after authentication; it is never in the source repo.
- OTA firmware updates over the LAN.

**Testing without hardware**

- A command-line **scan simulator** (Python) posts the same payload from saved tag dumps, so the server can be built and tested before the hardware exists. It imports dumps exported from a phone and strips the sector trailers, which hold the keys.
- A **screen simulator** runs the firmware's real LVGL screens on a PC at 320×240, with the keyboard as the three buttons and saved tag dumps as taps, against a real or test server.
- Firmware logic reaches the reader, buttons, screen and storage through interfaces, so it can run in PC unit tests with fakes.

## Server: data model

The server is event-sourced: every scan, AMS observation and UI edit is an immutable event, and each spool's current state is derived from its events. This makes undo and audit trivial.

**Stack**: Python 3.12, FastAPI, SQLAlchemy with SQLite (WAL mode), Alembic migrations, server-rendered UI (Jinja2 + HTMX), one Docker image.

**Tables**

| Table | Key fields | Purpose |
| --- | --- | --- |
| `product` | id, material\_id, variant\_id, filament\_type, color\_rgba, display\_name, low\_stock\_threshold | One row per filament product (for example Black PLA Basic); created automatically from the first decoded tag; display name editable |
| `spool` | id, tray\_uid (unique), product\_id, state, received\_at, opened\_at, emptied\_at, remaining\_pct, location, notes | One physical spool; state and timestamps derived from events |
| `tag` | uid (unique), spool\_id, raw\_blocks, decoded\_json, first\_seen\_at | Each spool has up to two tags; raw dump kept for re-decoding |
| `event` | id (UUID from device or server), spool\_id, type, source, device\_id, occurred\_at, payload\_json, reverted\_by | Append-only log; undo writes a new `revert` event |
| `device` | id, name, token\_hash, last\_seen\_at, fw\_version | Registered scanners |
| `printer` | id, name, serial, host | Printers watched over MQTT |

**Spool states and transitions**

| From | Event | To | Source |
| --- | --- | --- | --- |
| (none) | `received` | `sealed` | Scanner, UI |
| (none) | `opened` | `open` | Scanner, UI, AMS (implicit receive) |
| `sealed` | `opened` | `open` | Scanner, UI, AMS first sighting |
| `open` | `empty` | `empty` | Scanner, UI |
| `sealed` | `empty` | `empty` | Scanner, UI (flagged for review) |
| any | `revert` | previous state | Undo from scanner or UI |
| `empty` | `opened` | `open` | UI (correction); queued offline scan (flagged for review) |

**Decoding**

- A `decoder` module turns raw blocks into a typed record (material, variant, type, color, weight, diameter, temperatures, production date, tray UID).
- Decoding is pure and versioned; if the decoder improves, a maintenance command re-decodes every stored tag.
- Unknown or unreadable tags are stored in `tag` by UID with no spool and shown in Review as `unidentified`, so nothing is lost.

## Server: API

A versioned REST API under `/api/v1`, documented by FastAPI's generated OpenAPI page. Devices authenticate with a bearer token; the UI and Home Assistant use an admin token or session.

| Method | Path | Caller | Purpose |
| --- | --- | --- | --- |
| POST | `/scans` | Scanner | Submit a scan event; a lookup returns spool, product, state, allowed and suggested actions; an action returns the new state and a `feedback` code for the screen |
| POST | `/devices/heartbeat` | Scanner | Online status, firmware version, queue length |
| GET | `/devices/provisioning` | Scanner | Returns the key-derivation constant to an authenticated device |
| GET | `/inventory` | UI, HA | Counts by product and state, low-stock flags |
| GET | `/spools` | UI | List with filters: state, product, location |
| GET | `/spools/{id}` | UI | Spool detail with tags and event timeline |
| PATCH | `/spools/{id}` | UI | Edit location and notes |
| POST | `/spools/{id}/events` | UI | Manual action (received, opened, empty) |
| POST | `/events/{id}/revert` | UI, Scanner | Undo an event; a scanner can undo only events from its own device |
| GET / PATCH | `/products`, `/products/{id}` | UI | Display names and low-stock thresholds |
| GET / POST / DELETE | `/devices` | UI | Register a scanner and issue or revoke its token |
| GET | `/health` | Docker, HA | Liveness and dependency status |

**Scan response feedback codes**: `ok`, `ok_created` (implicit receive), `already_in_state`, `flagged` (out of order), `unreadable`, `error`. The device maps each to a screen message and sound.

**Idempotency**: a repeated `event_id` returns the original result without writing a second event.

## Server: web UI

A small, mobile-friendly web app for checking stock and fixing mistakes; day-to-day input comes from the scanner.

| Page | Shows | Actions |
| --- | --- | --- |
| Inventory | One card per product: color swatch, name, sealed / open / used-up counts, low-stock badge | Filter by type; sort by low stock |
| Spools | Table of spools with state, product, location, remaining %, dates | Filter, search, bulk change location |
| Spool detail | Tag data, AMS remaining %, event timeline | Manual action, undo, edit notes and location |
| Products | Decoded product IDs and colors | Set display name and low-stock threshold |
| Review | Flagged events, `unidentified` tags, "likely empty" suggestions | Accept, correct or dismiss |
| Devices | Scanners and printers with online status, firmware, queue | Register device, rotate token |
| Activity | Global event log, newest first | Undo |

The color swatch comes from the tag's RGBA value, so new colors appear correctly with no setup.

## Integrations

**Bambu P1S (local MQTT)**

- The server subscribes to the printer's local MQTT report (TLS, port 8883, LAN access code) for each configured printer.
- From each AMS tray it reads the tray UID, filament type, color and remaining %.
- A new tray UID triggers the automatic `opened` event (source `ams`); remaining % updates the spool in place, debounced to one write per change.
- Read-only, with one exception: the server may publish `pushall`, which requests full state, because P1 printers otherwise report only changes. It never publishes anything else to the printer.
- `PRINTERS` may point at an MQTT proxy instead of the printer, to stay under the printer's connection limit. Any proxy is a separate project, not part of this system.
- A **fake printer** replays recorded or documentation-based report messages over TLS, so this integration can be tested without a printer.
- Alternative (see Open questions): read the same data from the ha-bambulab entities in Home Assistant instead of a second MQTT connection.

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
- LAN-only; remote access through the existing home VPN, never exposed to the internet.
- Nightly SQLite backup (online backup API) to a second volume, 14 kept.

**Configuration** (environment variables or a `.env` file, never committed)

| Setting | Example | Purpose |
| --- | --- | --- |
| `ADMIN_TOKEN` | random 32 bytes | UI login and HA access |
| `BAMBU_KDF_SALT` | hex string | Key-derivation constant, served to provisioned devices |
| `PRINTERS` | name, host, serial, access code | Printers to watch over MQTT |
| `MQTT_URL`, `MQTT_USER`, `MQTT_PASSWORD` | HA broker | Discovery and state publishing |
| `HA_URL`, `HA_TOKEN` | long-lived token | Firing HA events |
| `TZ` | `America/New_York` | Timestamps in the UI |

**Security requirements**

- Every endpoint except `/health` requires authentication.
- Device tokens are stored hashed, revocable, and scoped to `/scans`, `/devices/heartbeat`, `/devices/provisioning` and `/events/{id}/revert` for events from that same device.
- Input validation on all payloads (Pydantic); block arrays capped in size.
- No tag UIDs or derived keys in logs above debug level, in line with the RFID guide's request not to publish UID/key pairs.
- The printer access code and HA token never leave the server or appear in API responses.

## Testing

The server is fully testable without hardware. Firmware logic is unit tested on a PC, and hardware behavior gets a short manual checklist.

| Layer | What is tested | How |
| --- | --- | --- |
| Decoder | Every field; two rolls of the same product yield the same product key | pytest against generated tags in CI, plus own spools and the public Bambu RFID library locally |
| State machine | Every transition in the table, out-of-order flags, undo | pytest, property tests for event replay |
| API | Auth on every route, idempotent scans, validation errors | pytest with FastAPI TestClient |
| Security | Unauthenticated access refused, revoked tokens refused, oversized payloads rejected | pytest security suite, run in CI |
| AMS ingest | Report messages produce the right events | Fake printer replaying recorded or documentation-based messages |
| End to end | Scan simulator drives Received, Opened, Empty for a spool; HA entities update | Docker Compose test stack with a Mosquitto container |
| Firmware logic | Screen flow, tag parsing, offline queue, dedupe, button thresholds | PC unit tests with fakes; 90% coverage, excluding a named list of hardware drivers |
| Firmware screens | Every screen and soft-key mapping | Screen simulator |
| Firmware on hardware | Read through lid and box, each soft key and touch target, menu navigation, timeout, offline queue, OTA, plus the excluded drivers | Manual checklist per release |

Public and personal tag dumps contain UIDs and keys. They are used locally and never stored in the repo; CI uses generated tags only.

A `CLAUDE.md` in the repo sets the build guardrails: work only from this spec, tests and security tests with every change, feature branches, and spec changes committed with the work they cover.

## Milestones

Each milestone ends with something usable. Reading is proved first with a phone, so the software can be built before the scanner hardware arrives; the PN532 proof follows when it does.

1. **M0a Prove reading, phone**: dump two rolls of the same product with an Android app; confirm matching product fields and distinct tray UIDs; try reading through the shipping box.
2. **M1 Server core**: decoder, data model, event log, `/scans` API, scan simulator, tests.
3. **M2 Web UI**: inventory, spools, spool detail, review, devices.
4. **M5 Printer link**: P1S MQTT ingest, automatic Opened, remaining %, likely-empty suggestions, built against the fake printer and checked against the real P1S.
5. **M6 Home Assistant**: MQTT discovery entities, events, low-stock automation.
6. **M3a Firmware without hardware**: scan flow, offline queue and dedupe logic with PC tests, screen simulator.
7. **M0b Prove reading, PN532**: repeat the read tests on the bench rig and measure reading through the 1 mm lid and shipping box.
8. **M3b Firmware on hardware**: breadboard build, real drivers, provisioning, OTA.
9. **M4 Enclosure**: printed case, button labels, antenna placement, final wiring.
10. **M7 Later**: see Future enhancements.

## Future enhancements

- **Custom PCB scanner (v2)**: replaces the CYD prototype once the screen and menu flow are settled. ESP32-S3 module, PN532 and a tuned antenna on board, SPI touch TFT, three dedicated button inputs (no resistor ladder), front-facing RGB LED, buzzer, and USB-C power with an optional PoE variant, following the Harmony Hub replacement PCB work.
- **Load-cell scale**: weigh a spool for remaining grams when it is not in the AMS.
- **Spoolman sync**: one-way export, as described under Integrations.
- **Non-Bambu filament**: NTAG stickers in an open format, or QR labels printed by the server.
- **Second scanner by the printer**: same firmware, its own device token.

## Open questions

- [ ] Does a tag read through the sealed shipping box with the PN532, and from which side? If not, New needs another trigger (box barcode, or scanning at first opening). A Pixel 9 Pro XL has read a tag through one box, contents not recorded, but a phone antenna is not a PN532.
- [ ] Does the AMS tray UUID equal the tag's tray UID, and how does the AMS report non-Bambu spools? Check against the real P1S.
- [ ] Buttons on the CYD prototype: resistor ladder on GPIO35, or a PCF8574 expander?
- [ ] Printer data source: direct MQTT from the server, or the ha-bambulab entities in Home Assistant?
- [ ] Do Bambu refill packs carry the same tags, and how should a refill on a reused spool be tracked?
- [ ] Project and repo name.
