# Progress

## Done

- Spec and enclosure design committed.
- README.md added, and AGENTS.md now requires keeping it up to date.
- M0a partly done: a Pixel 9 Pro XL running BambuTagScanner read filament tags, including through one box with contents not recorded.
- M0a two-roll comparison passed (2026-11-05): two Black PLA Basic rolls decoded with the new decoder to the same product key (GFA00, A00-K00, 000000FF) and different tray UIDs. Production dates differ by minutes on the same day.
- M0a further results (2026-11-05): both PLA rolls were refills, read through their sealed boxes from either side; both tags of one roll share a tray UID; TPU in its foil bag cannot be read.
- M0a complete (2026-11-05): older ABS and PETG spools, not refills, also read through their sealed boxes once the phone was held still. Reading through the box with a PN532 is still open for M0b.
- Spec updated: manual entry of spools whose tags cannot be read yet (placeholder spools linked on first scan, provisional products), and the rule for `received` on an open or empty spool.
- Spec updated with the approved gap fixes, test tools and milestone order; `nfc_skin` set to 1.0 mm.
- Enclosure manifest renamed to `manifest.json`.
- Server skeleton with a health check, plus CI for lint, tests, the 90% coverage gate and a dependency audit.
- Bill of materials (`hardware/BOM.md`) merged.
- M1 part 1, the decoder, merged (PR #6).
- M1 part 2, settings, tables and migrations, merged (PR #7).
- M1 plan approved: five branches merged in order (decoder, data model, event log, `/scans` API, scan simulator).

## In progress

- `feature/event-log` (M1, part 3 of 5): spool state machine and replay, scanner action menus, and the event log service (append, undo, re-projection). Spool state may now be null (Unknown).

## Next

- M0b hardware ordered (2026-11-05): CYD, two PN532 V3 modules, JST 1.25 mm 4-pin pigtails, breadboard and jumpers, 12 × 12 × 7.3 mm tactile switches, resistors, and cavity speakers. M0b starts when it arrives.
- M1 part 4, `feature/scans-api`: `/scans`, device registration and tokens, `/events/{id}/revert`, placeholder linking.
- M1 part 5, `feature/scan-simulator`.

## Decisions

- 2026-10-31: Use the resistor ladder on GPIO35 for the buttons, because its voltages are well separated and it needs no extra chip. The PCF8574 stays as the fallback.
- 2026-10-31: Keep all agent instructions and build commands in AGENTS.md, with no CLAUDE.md, so every tool follows one file.
- 2026-10-31: Use uv for dependency locking because it is already installed and needs no extra lock tool.
- 2026-10-31: Branches use the `feature/...` naming from AGENTS.md, because project rules win over the global `feat/...` convention.
- 2026-10-31: Order the milestones as M0a, M1, M2, M5, M6, M3a, M0b, M3b, M4, because the hardware has not arrived and a phone can settle most of the reading risk first.
- 2026-10-31: Use BambuTagScanner for M0a instead of writing an Android app. A static review found no signs of malware and no internet permission, but did not prove the APK matches its source.
- 2026-10-31: Firmware coverage of 90% applies to PC-testable logic, with a named driver exclusion list, because drivers need real hardware.
- 2026-10-31: Keep tag dumps out of the repo because they contain UIDs and keys, and the public library is GPL-3.0. CI uses generated tags.
- 2026-10-31: Any printer MQTT proxy stays a separate project; `bradsjm/bambu-mqtt-proxy` is the first to try if the connection limit is hit.
- 2026-10-31: The README mockup link uses the OpenSCAD edition of the viewer, because the manifest has only `.scad` parts and the repo has no STLs.

- 2026-11-05: M1 includes `/scans`, `/devices` registration and `/events/{id}/revert`; heartbeat and provisioning wait for M3a, when the firmware needs them.
- 2026-11-05: A `received` event for a spool that is already open or empty is recorded and flagged for review, with no state change. A second roll of the same product has its own tray UID, so it is a new spool.
- 2026-11-05: Spools whose tags cannot be read yet (for example TPU in a foil bag) are added by hand in the web UI as placeholders with no tray UID; the first scan of that product's tag links to the oldest placeholder and is flagged for review. Unknown products are created by hand as provisional. The data model in M1 allows this; the UI comes in M2.
- 2026-11-05: Lookups do not write events; only actions are logged.
- 2026-11-05: The scan simulator reads BambuTagScanner's export (a ZIP or a 1024-byte `.bin` image with sector trailers) and strips the trailers so keys are never sent.
- 2026-11-05: The decoder rejects a tag with no material ID or an all-zero tray UID as unreadable. Fields the RFID guide marks as uncertain decode to null when their bytes are unusable.
- 2026-11-05: The synthetic tag generator lives in the package (`decoder/synthetic.py`), not in `tests/`, because the scan simulator's `generate` command uses it too.

- 2026-11-05: Migrations live inside the package (`filament_tracker/migrations`) instead of `server/migrations`, so they ship with the installed server and the Docker image.
- 2026-11-05: Timestamps are stored as UTC and refused if they have no timezone. Events also store `recorded_at` (arrival time) and a `flagged` flag; replay orders by `occurred_at`, then `recorded_at`.
- 2026-11-05: Device IDs are strings chosen at registration. Revoking a device sets `revoked_at` rather than deleting it, so its events keep their link.
- 2026-11-05: `low_stock_threshold` defaults to 0, which means no low-stock alert until one is set.

- 2026-11-05: Repeated actions (`already_in_state`) are still stored as events. They change nothing, but keep the audit trail complete, and they take effect if an earlier event is undone.
- 2026-11-05: A spool's state is null (Unknown) after every event that set it is undone; the spool row and its tags are kept. Added to the spec and as a migration.
- 2026-11-05: Reopening an empty spool from the UI is a correction and is not flagged; from a scanner (a queued scan) it is flagged. A reopened spool keeps its first `opened_at` and clears `emptied_at`.
- 2026-11-05: Undoing an undo, or undoing an event twice, is refused.

## Open questions

- The case model must be adjusted for the speaker that was ordered: a 15 × 10 × 3.5 mm rectangular cavity speaker (8 Ω, JST PH 1.25 mm plug, 80 mm lead) instead of the 20 mm round one in `filament-scanner-case.scad`. Replace the round holder with a rectangular one and resize the grille. Before changing it, check on the real parts which face the sound opening is on and where the CYD's speaker socket is. The lead may need an extension or a splice to reach the socket. Update BOM item 5 at the same time. Due by M4.
- The user will confirm on the real parts and report back: JST connector sizes, the CN1 pinout, CC pull-downs on the USB-C breakout, two-supply protection on the CYD, and whether the CYD's 3.3 V supply can power the PN532.
- `fastapi.testclient` warns that using httpx with Starlette's test client is deprecated and suggests `httpx2`. Tests pass. Vet `httpx2` and get approval before switching.
- `.env.example` was not added because agent permission settings block writing it. Settings are documented in the spec's Configuration table.

See also the Open questions section of docs/SPEC.md.
