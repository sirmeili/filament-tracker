# Rollcall (working name; formerly Filament Tracker)

A self-hosted system that tracks every Bambu Lab filament spool from delivery to empty, using the RFID tags already on the spools. Tap a spool on a small touchscreen scanner (or an Android phone running the companion app), confirm whether it is new, just opened or empty, and a central server keeps the inventory, feeds Home Assistant and serves a web app for a few users.

It runs in Docker with no Bambu cloud dependency. Scanners and integrations stay on your LAN; the web app, with personal accounts and Viewer, Editor and Admin roles, can be reached from the internet through your own HTTPS reverse proxy.

Planned after deployment: print requests. A co-owner of the printer submits models, picks filament from what is in stock or from the full Bambu catalog (from the Open Filament Database), and follows each print to pick-up, with filament held for accepted requests and a shopping list. The name Rollcall is a working name (it replaced Spoolhouse); the repo is `sirmeili/rollcall`, and the code still uses Filament Tracker until the rename. See Future enhancements: print requests in [docs/SPEC.md](docs/SPEC.md).

> **Status: early development.** This repo currently holds the spec, the enclosure design and the server core (M1): the tag decoder, the database, the event log, the scanner API (`/scans`, device registration and undo) and a scan simulator. M2 is complete: user accounts with Viewer, Editor and Admin roles, sign-in sessions, LAN-only tokens and the API behind the pages are built, and the web app has sign-in, a Light/Dark/System theme and every M2 page: Inventory, Spools, Spool detail, Products, Review, Activity, adding a spool by hand, Devices, Users and Account. The server also accepts the scanner heartbeat. M5 (the printer link) has started: the server connects to printers over MQTT (directly or through an MQTT proxy, with the certificate pinned on first use) and reads AMS reports into spools, slots and likely-empty suggestions, which the Devices, Review, Spools and Spool detail pages show. It has been checked against a real P1S with an AMS and an AMS HT, so M5 is complete. M6 (Home Assistant) is complete: the server publishes inventory and low-stock entities to Home Assistant through MQTT discovery, and fires Home Assistant events for spool actions and low stock, with an example low-stock automation. Admins can set the Home Assistant connection on a Settings page, with passwords and tokens stored encrypted, and changes apply without a restart. `ft-ha check` compares what the server publishes with what Home Assistant shows, and it has been checked against a real Home Assistant with the Mosquitto add-on. M8 is complete: an Android phone app that works as a scanner; the server now hands the tag key constant to paired devices, and Devices shows a pairing QR code. The phone app's Scan and Pairing screens, offline queue and on-phone decoding are built into the web app, and the Android app around them (Capacitor, with a Kotlin plugin for NFC tag reading, QR scanning and Keystore storage) has passed its manual checklist on a Pixel 9 Pro XL, which completes M8. M9 (Deployment) has started: the Settings page also sets the time zone every time in the web app is shown in, how long a sign-in lasts and the tag key constant, and admins add, edit, test and remove printers on the Devices page, with access codes stored encrypted. Admins also make machine tokens for Home Assistant and scripts on the Settings page, each with a role, shown once and revocable. A new server opens a first-start Setup page (from the LAN, with a one-time code from the server's log) that creates the first Admin. Rollcall now runs as one Docker image (`ghcr.io/sirmeili/rollcall`, private, built and tested end to end by GitHub Actions) with Docker Compose, and backs its database up every night; see [docs/deploy.md](docs/deploy.md). The Scan screen has since been redesigned from the mockups in `docs/mockups/mobile-scanner/` for one-handed use, with countdown bars, a Scan button in the full app, and a Delivery mode that lists every spool scanned while unpacking a box. The other features described below have not been built yet, and most of the software is planned to be built before the scanner hardware arrives. See [PROGRESS.md](PROGRESS.md) for current work.

[![Filament scanner case](hardware/enclosure/preview.png)](https://sirmeili.github.io/3d-mockup-viewer/openscad/viewer.html?manifest=https://raw.githubusercontent.com/sirmeili/rollcall/main/hardware/enclosure/manifest.json)

## Goals

- See at a glance how many sealed and open spools exist for each filament (for example: Black PLA Basic, 3 sealed, 1 open).
- Record each spool's lifecycle with one tap and one confirm: New, Opened, Empty.
- Identify spools from their Bambu RFID tags, with no manual typing of type or color.
- Use P1S/AMS telemetry to fill in what the printer already knows: when a spool was first loaded and its remaining %.
- Surface low-stock alerts and inventory sensors in Home Assistant.

Writing or cloning tags, load-cell weighing, third-party filament without Bambu tags and slicer integration are out of scope for v1.

## How it works

1. **Tap.** The scanner reads the tag and asks the server what it knows about the spool.
2. **Confirm.** The screen shows the product, a color swatch and the current state, and highlights the suggested action. Confirm with one of the three buttons or by touch.
3. **Record.** The server logs the event and updates the inventory. If the server is unreachable, the scanner queues the event and retries.

Each spool carries two tags with different UIDs but the same tray UID. The tray UID is the spool's identity, so either tag works.

## Components

| Component | Role | Planned stack |
| --- | --- | --- |
| Scanner | Reads tags, derives keys and posts raw tag data; shows the spool and takes the action | ESP32 "Cheap Yellow Display", PN532 reader, three soft-key buttons; PlatformIO, Arduino, LVGL |
| Phone scanner | An Android phone as a scanner (on phones whose NFC supports MIFARE Classic), plus the full web app; paired by a QR code from the Devices page | Capacitor around the web app, with a Kotlin NFC plugin |
| Server | Decodes tags, stores every change as an immutable event, derives spool state and serves the API | Python 3.12, FastAPI, SQLAlchemy, SQLite, Alembic |
| Web UI | Check stock, fix mistakes and manage products, devices and users | SvelteKit (TypeScript), built to static files served by the server |
| Printer link | Reads AMS trays read-only to detect opened spools and track remaining % | Local MQTT from the P1S |
| Home Assistant | Inventory and low-stock entities, plus events for automations | MQTT discovery, REST API |
| Scan simulator | Replays saved tag dumps so the server can be tested without hardware | Python |
| Screen simulator | Runs the real scanner screens on a PC, with the keyboard as buttons | LVGL |
| Fake printer | Replays AMS report messages over TLS so the printer link can be tested without a printer | MQTT |

## Enclosure

The scanner case is a parametric OpenSCAD model with the screen and buttons on the front and a flat "tap here" zone over the PN532 antenna. It holds the CYD, the PN532, the button board, a speaker and a USB-C power input. It is designed to mount on a wall by keyhole screws, magnets or Command strips, and can also sit on a shelf.

Select the image above to open the interactive 3D mockup. The source is in [hardware/enclosure/](hardware/enclosure/):

- [filament-scanner-case.scad](hardware/enclosure/filament-scanner-case.scad): the OpenSCAD model
- [manifest.json](hardware/enclosure/manifest.json): the part list and groups for the mockup viewer
- [preview.png](hardware/enclosure/preview.png): the rendered preview

## Roadmap

| Milestone | Scope |
| --- | --- |
| M0a Prove reading, phone | Dump two rolls of the same product with an Android app; confirm matching product fields and distinct tray UIDs; try reading through the shipping box |
| M1 Server core | Decoder, data model, event log, `/scans` API, scan simulator, tests |
| M2 Web UI | User accounts and roles, inventory, spools, spool detail, products, review, activity, devices, users, manual entry |
| M5 Printer link | P1S MQTT ingest, automatic Opened, remaining %, likely-empty suggestions |
| M8 Phone scanner | Android app (Capacitor around the web app, Kotlin NFC plugin), QR pairing, offline queue |
| M6 Home Assistant | MQTT discovery entities, events, low-stock automation, the Settings page with the Home Assistant settings |
| M9 Deployment | Printers and the remaining settings in the app, machine tokens, first-start setup, Docker image and Compose file, nightly backups |
| M10 Print requests, Phase 2 | Filament catalog and Bambu color codes, the Requester role, print requests and their status pipeline, holding filament, shopping list |
| M11 Print requests, Phase 3 | Reading 3MF files, print jobs from the printer, push notifications, picking colors on the model, MCP server |
| M3a Firmware without hardware | Scan flow, offline queue and dedupe logic with PC tests, screen simulator |
| M0b Prove reading, PN532 | Repeat the read tests on the bench rig; measure reading through the lid and shipping box |
| M3b Firmware on hardware | Breadboard build, real drivers, provisioning, OTA |
| M4 Enclosure | Printed case, button labels, antenna placement, final wiring |
| M7 Later | Future enhancements listed in the spec |

## Repository layout

```text
docs/SPEC.md                  Full specification: the source of truth
docs/deploy.md                Running Rollcall with Docker Compose: setup, proxy, backups, updates
docs/mockups/web/             Web app page mockups and design tokens
docs/mockups/mobile-scanner/  Phone app Scan screen mockups
hardware/BOM.md               Bill of materials for one scanner
hardware/enclosure/           3D model of the scanner case
server/                       FastAPI server: decoder, database, event log, API, scan simulator
web/                          SvelteKit web app (TypeScript), built to static files the server serves
android/                      Android phone app: Capacitor around the web app, Kotlin NFC plugin
Dockerfile                    The image: the web app built with Node, served by the Python server
deploy/                       Compose file and example settings for the home server; deploy/test/ is the end-to-end test stack
.github/workflows/            CI: lint, tests, 90% coverage gates, dependency audits, end-to-end tests; the image build, test and publish
AGENTS.md                     Rules for AI agents working in this repo
PROGRESS.md                   Current status, next steps and decisions
```

## Documentation

[docs/SPEC.md](docs/SPEC.md) covers workflows, hardware, firmware, the data model, the API, security, testing and open questions.

Secrets such as the tag key-derivation constant, tokens and the printer access code are supplied as configuration and are never committed.

## Development

The server needs Python 3.12 and [uv](https://docs.astral.sh/uv/). From `server/`:

```sh
uv sync                # Install dependencies
uv run pytest          # Run tests with the 90% coverage gate
uv run ruff check .    # Lint
uv run uvicorn filament_tracker.main:create_app --factory --reload
```

The web app needs Node.js 24. From `web/`:

```sh
npm ci                 # Install dependencies
npm run test:coverage  # Run tests with the 90% coverage gate
npm run build          # Build to web/build, which the server serves at /
```

The Android app needs JDK 21 and the Android SDK (Android Studio installs it). From `web/`, then `android/`:

```sh
npm run build && npx cap sync android   # Copy the web app into the Android project
./gradlew coverageCheck                 # Kotlin tests with the 90% coverage gate
./gradlew assembleDebug                 # Build app/build/outputs/apk/debug/app-debug.apk
```

To install the app, run a phone test and work through the phone checklist, see [android/README.md](android/README.md).

To build and run the Docker image, from the repository root:

```sh
docker build -t rollcall:test .
cd server && FT_COMPOSE_STACK=1 uv run pytest tests/deploy --no-cov   # The end-to-end test stack
```

To run it on a server, see [docs/deploy.md](docs/deploy.md).

To create accounts (`ft-admin`), run behind a reverse proxy, register a scanner and use the scan simulator (`ft-sim`) with your own tag dumps, see [server/README.md](server/README.md).

The server keeps its SQLite database in `server/data/` by default (set `DATABASE_URL` to change it) and applies migrations on startup.
