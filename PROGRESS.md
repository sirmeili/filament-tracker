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
- M1 part 3, state machine, replay and event log, merged (PR #8).
- M1 part 4, `/scans`, device registration, revert and auth, merged (PR #9).
- M1 part 5, the `ft-sim` scan simulator, merged (PR #10). **M1 complete.**
- Real BambuTagScanner dumps run through `ft-sim` against a local server: both Black PLA Basic refills recorded as sealed spools (same product name; one product not yet confirmed with `--json`).
- M2 plan approved: seven branches (spec, users and auth, read API, write API, web foundation, stock pages, admin pages).
- M1 plan approved: five branches merged in order (decoder, data model, event log, `/scans` API, scan simulator).

## In progress

- `feature/m2-spec` (M2, part 1 of 7): spec for user accounts and roles, public access through an HTTPS reverse proxy with scanner routes LAN-only, the SvelteKit web app, review actions and the low-stock rule. `ft-sim` now says when a wildcard matches nothing and prints the spool number. Accepted by the user; PR open, awaiting merge.

## Next

- M0b hardware ordered (2026-11-05): CYD, two PN532 V3 modules, JST 1.25 mm 4-pin pigtails, breadboard and jumpers, 12 × 12 × 7.3 mm tactile switches, resistors, and cavity speakers. M0b starts when it arrives.
- M2 part 2, `feature/users-auth`: users, sessions, roles, `ft-admin`, LAN-only bearer tokens, sign-in throttling, security headers.
- M2 parts 3 to 7: read API, write API, SvelteKit foundation, stock pages, admin pages.

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

- 2026-11-05: Device tokens look like `ftd_<random>`, are shown once at registration and stored as SHA-256 hashes. Admin routes are closed if `ADMIN_TOKEN` is not set. The admin token cannot submit scans; device tokens cannot use admin routes (both get 401).
- 2026-11-05: A scan's `device_id` must match its token (403). An `event_id` already used by another device is refused (409). Each action event stores its response, which is returned unchanged on retry.
- 2026-11-05: A tag whose UID disagrees with block 0, or whose blocks do not decode, is unreadable; it is kept by UID with its raw blocks for later re-decoding. A failed read never overwrites a tag already known.
- 2026-11-05: New products get the default name "<detailed type> #<RRGGBB>", editable in M2.
- 2026-11-05: A provisional product is matched by filament type and color when it has unlinked placeholders; only a single match is used, and it is filled in with the tag's IDs (added to the spec).
- 2026-11-05: Request bodies are capped at 16 KiB (413), checked from Content-Length and while streaming.
- 2026-11-05: Fixed: synthetic tags regenerated their random filler on every read; they now read the same every time.

- 2026-11-05: `ft-sim` uses only the standard library for HTTP, so the server needs no new runtime dependency. It expands wildcards itself because PowerShell does not, and masks the tag UID that BambuTagScanner puts at the start of its file names.
- 2026-11-05: `ft-sim generate` writes a tag file instead of posting directly, so the same synthetic spool can be scanned through its whole life. `*.zip` is now ignored by git, alongside `*.bin`.

- 2026-11-05: The web app gets personal accounts with Viewer, Editor and Admin roles; the first admin comes from the `ft-admin` command, never a default account. Passwords use Argon2id, at least 12 characters.
- 2026-11-05: The web app may be public, but only behind the owner's HTTPS reverse proxy. Scanner routes, bearer tokens (device and admin) and the API docs are accepted only from `TRUSTED_NETWORKS`. This replaces the spec's "LAN-only, never exposed" rule.
- 2026-11-05: The web UI is a SvelteKit single-page app (TypeScript), built to static files that FastAPI serves, instead of Jinja2 + HTMX. Production stays one Python process; Node.js is only needed to build and test. Styling is hand-written component CSS.
- 2026-11-05: Browser sign-in uses a server-side session (cookie HttpOnly, Secure, SameSite=Strict, 30 days); state-changing cookie requests also need an `X-Requested-With: filament-tracker` header.
- 2026-11-05: Review actions for a flagged event: Accept (correct), Undo (revert) or Open spool (fix by hand). Low stock means the sealed count is at or below the product's threshold; 0 turns it off.
- 2026-11-05: `ADMIN_TOKEN` stays for machine access (Home Assistant, scripts) and is accepted only from the LAN; people use accounts.

## Open questions

- The case model must be adjusted for the speaker that was ordered: a 15 × 10 × 3.5 mm rectangular cavity speaker (8 Ω, JST PH 1.25 mm plug, 80 mm lead) instead of the 20 mm round one in `filament-scanner-case.scad`. Replace the round holder with a rectangular one and resize the grille. Before changing it, check on the real parts which face the sound opening is on and where the CYD's speaker socket is. The lead may need an extension or a splice to reach the socket. Update BOM item 5 at the same time. Due by M4.
- The user will confirm on the real parts and report back: JST connector sizes, the CN1 pinout, CC pull-downs on the USB-C breakout, two-supply protection on the CYD, and whether the CYD's 3.3 V supply can power the PN532.
- `fastapi.testclient` warns that using httpx with Starlette's test client is deprecated and suggests `httpx2`. Tests pass. Vet `httpx2` and get approval before switching.
- `.env.example` was not added because agent permission settings block writing it. Settings are documented in the spec's Configuration table.

See also the Open questions section of docs/SPEC.md.
