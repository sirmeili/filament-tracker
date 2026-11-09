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
- M2 part 1, the spec for accounts, public access and the SvelteKit app, merged (PR #11).
- M2 part 2, user accounts, sessions, roles and LAN-only tokens, merged (PR #12).
- M2 part 3, the read API for inventory, products, spools, activity and review, merged (PR #13).
- M2 part 4, the write API (edits, manual entry, review, token rotation), merged (PR #14).
- M2 part 5, the SvelteKit web foundation (sign-in, layout, navigation by role, served by FastAPI), merged (PR #15).
- Web app mockups (direction A, "Workshop") and the owner's decisions on them, merged (PR #16).
- Scan redesign part 1, the one-spool Scan screen from the mockups, a Scan button in the full app, a 15 s limit on web app requests, and the queue sent as soon as the server answers, merged (PR #31).
- M6 part 2, Home Assistant events and an example low-stock automation, merged (PR #29).
- M2 part 6, the Inventory, Spools, Spool detail and Products pages with the mockup look and a Light/Dark/System theme, merged (PR #17).
- Phone scanner (M8) added to the spec, merged (PR #19).
- M5 part 1, reading AMS reports into spools, slots and likely-empty suggestions, merged (PR #20).
- M5 part 2, the MQTT link with certificate pinning and the fake printer, merged (PR #21).
- M5 part 3, the printer pages: Printers on Devices, likely-empty Dismiss on Review, the AMS slot on spools, merged (PR #22).
- M5 part 4, checked against the real P1S, AMS HT units and `ft-printer check`, merged (PR #23). **M5 complete.**
- M6 part 1, Home Assistant entities through MQTT discovery (Total spools, Total open, Total sealed, Spools in review, Low filament), merged (PR #28).
- M8 part 1, `BAMBU_KDF_SALT`, `/devices/provisioning`, `ft-sim check-salt` and the pairing QR code, merged (PR #24).
- M8 part 4, the phone checklist on a Pixel 9 Pro XL and the fixes it found (no plugin data in the phone's log, loopback addresses refused, a 5 s request limit, one read at a time, a beep and buzz after a full read), merged (PR #27). **M8 complete.**
- M8 part 3, the Android app with its Kotlin NFC plugin, Keystore storage, QR scanning and the Android CI job, merged (PR #26).
- M6 part 3, the Settings page with the Home Assistant settings, secrets encrypted with `SETTINGS_KEY` or `settings.key`, applied without a restart, merged (PR #34).
- M6 part 4, `ft-ha check` and the Home Assistant checklist, run against the owner's Home Assistant (2026-11-09): all 5 entities match the broker, and all 8 checklist steps passed. PR #36 from `feature/ha-check`. **M6 complete.**
- M8 part 2, the phone app's logic in the web app (bridge interface, pairing, device API, offline decode and queue, Scan flow, Scan and Pairing pages), merged (PR #25).
- M2 part 7, the Review, Activity, Devices, Users and Account pages, manual entry, Review Bring back, the scanner heartbeat and the Activity source filter, merged (PR #18). **M2 complete.**
- M2 plan approved: seven branches (spec, users and auth, read API, write API, web foundation, stock pages, admin pages).
- M1 plan approved: five branches merged in order (decoder, data model, event log, `/scans` API, scan simulator).

## In progress

- M9, Deployment. Plan approved (2026-11-09): five branches merged in order (General and Scanners settings in the app, with the repo rename and the M9 spec decisions; printers on the Devices page; machine tokens; first-start setup; the Docker image, Compose file, nightly backups and the image published to GHCR, then a walkthrough on the owner's home server).
- `feature/settings-general` (M9 part 1):
  - Done: the GitHub repo renamed to `sirmeili/rollcall` (the old address redirects) and the local remote updated; the spec and README use the working name Rollcall; the spec records the M9 decisions (a private `ghcr.io/sirmeili/rollcall` image for x86-64 built by GitHub Actions, Docker Compose on the owner's home server, the time zone setting covering every time in the web app and the 03:00 backup, `UTC` by default). `tzdata` added to the server (no advisories; the time zone database Python lacks on Windows).
  - Done (server): the General (`tz`, `session_days`) and Scanners (`bambu_kdf_salt`, stored encrypted) settings groups. New sign-ins use the saved sign-in length, `/devices/provisioning` serves the saved salt, `/auth/me` returns the time zone, and `ft-sim check-salt` checks the salt in use (read with `ft-ha check`'s read-only settings code, now `app_settings/offline.py`). `TZ` in `.env` is checked against the time zone names and defaults to `UTC`.
  - Next: the Settings page shows the General and Scanners groups, and the web app shows every time in the server's time zone.
- Phone Scan screen redesign, from the mockups in `docs/mockups/mobile-scanner/` (merged in PR #30). Plan approved (2026-11-06): two branches, before M6 part 3.
- Phone Scan screen redesign complete: part 1 merged in PR #31, part 2 (the Delivery mode) in PR #32.
- Settings spec merged (PR #33).
- M6 part 3 merged (PR #34).
- Print requests direction added to the spec (PR #35).
- Done, PR #32 (part 2, the Delivery mode): a Delivery toggle on the waiting screen; while it is on, the top of Scan lists the spools recorded in the session (color, name, time, number, queued until sent, Undone), with totals and Clear, and the bottom is one panel (Ready, the spool with its keys and 15 s bar, then what was recorded with Undo and a 3 s bar). Only the newest row has Undo. The list is kept in memory until the app closes (leaving Scan keeps it) and cleared when the pairing is forgotten. The last scan now carries the spool as the server has it, so a new tag's row shows its number. The Delivery button widens to fit its label at large phone text sizes, and the Ready icon pulses like the waiting screen's target. Spec updated (Phone scanner, Unpacking a delivery).

## Next

- M10 and M11, print requests Phase 2 and Phase 3 (see SPEC Future enhancements: print requests), before the firmware milestones.
- Later (owner's request, 2026-11-06, in SPEC Future enhancements): the theme choice moves to the Account page; a phone app setting for the start screen (Scan or the web app); a bottom bar on phones with a menu button, Scan and the user.
- M0b hardware ordered (2026-11-05): CYD, two PN532 V3 modules, JST 1.25 mm 4-pin pigtails, breadboard and jumpers, 12 × 12 × 7.3 mm tactile switches, resistors, and cavity speakers. M0b starts when it arrives.

## Decisions

- 2026-11-09: M9 decisions (owner). Working name Rollcall, replacing Spoolhouse, still not final; the repo is renamed now. The server runs in Docker Compose on the owner's home server (an Intel x86-64 machine), from a private image on GitHub's container registry built by GitHub Actions. The time zone setting sets every time the web app shows and when the nightly backup runs.
- 2026-11-07: Print requests direction (owner). Working name Spoolhouse, not final; the rename waits until the name is settled, and reinstalling the phone app and renaming the Home Assistant names are accepted. One app with an Inventory module and a Print Requests module that depends on it, never the reverse. The whole web app stays reachable from the internet; only scanning stays on the LAN. A Requester role is added alongside Viewer, Editor and Admin. Phases 2 and 3 come after M9 and before the firmware milestones. The MCP server is the first in the owner's apps and must cover the examples given.
- 2026-11-07: Most settings move into the app, with `.env` as the starting value and a value saved in the app winning (this reverses the M6 part 3 plan, where `.env` won). Settings that could lock the admin out or open LAN-only routes stay in `.env` only. First start uses a Setup page instead of `ft-admin`, guarded by `TRUSTED_NETWORKS` and a one-time code in the server log. Deployment becomes milestone M9.
- 2026-11-06: Scan screen decisions (owner): the Delivery session list lasts until the app is closed, with a Clear button; View spool and Scan next on the result; the Scan theme toggle is the web app's theme choice; the full app gets a Scan button in its header in the phone app.
- 2026-11-06: Home Assistant events are found by reading new events from the database every 5 seconds, like the entities, so every source is covered; only events after the server starts are fired, so a restart never replays history into automations.
- 2026-11-06: Home Assistant entities come from a 5-second snapshot of the database, published only when changed, because it covers every way stock changes without hooking each write path.
- 2026-11-06: Home Assistant settings will also be editable on an Admin Settings page (owner's choice), with secrets encrypted in the database and `.env` values taking precedence.
- 2026-11-06: Build the Android app with JDK 21, because Gradle 8.14 cannot run on Android Studio's bundled JDK 25.
- 2026-11-06: Scan pairing QR codes with Google's code scanner (Play services), because it needs no camera permission and keeps camera code out of the app.
- 2026-11-06: Allow plain HTTP in the Android platform settings and enforce "LAN addresses only" when pairing, because Android's network rules cannot express private address ranges.
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
- 2026-11-06: An Android phone can be a scanner (M8, after M5). Browser NFC reads only NDEF, so it cannot read MIFARE Classic blocks; the app is a Capacitor wrapper around the web app with a Kotlin `MifareClassic` plugin. It also holds the full web app, uses Capacitor's native HTTP so the server needs no CORS, pairs by a QR code shown once on the Devices page, queues offline like the scanner, and allows plain HTTP on the LAN (signing in over plain HTTP needs `COOKIE_SECURE=false`, so pairing with the proxy's HTTPS address is recommended).
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
- 2026-11-05: A valid token or session on a route it may not use now gets 403 (it was 401); 401 means not signed in or an invalid token. Bearer tokens from outside `TRUSTED_NETWORKS` get 403.
- 2026-11-05: `ADMIN_TOKEN` acts as an Admin (devices, users, undo) from the LAN. Undo is open to Editors, the admin token, and a scanner for its own events; a web undo records the user.
- 2026-11-05: Added `COOKIE_SECURE` (default true) for signing in over plain HTTP during development, and `ft-admin reset-password` to recover a locked-out Admin. `/auth/logout` needs no session: without one it just clears the cookie.
- 2026-11-05: Sign-in throttling is kept in memory (5 failures per username, 20 per address, in 15 minutes), which suits one server process; a restart clears it. Unknown usernames are checked against a dummy hash so timing does not reveal them.
- 2026-11-05: The API docs get a looser Content Security Policy (they load Swagger UI and ReDoc from a CDN) and are served only to the LAN; everything else gets `default-src 'self'`.
- 2026-11-05: Inventory lists every product, including those with no spools, so a product with a threshold and nothing sealed shows as low. Spools whose events were all undone count as `unknown`.
- 2026-11-05: Until review accept arrives in part 4, Review shows every flagged event that has not been undone. "Likely empty" is an empty list until the AMS work in M5.
- 2026-11-05: Read responses never include a tag's raw blocks, only its decoded fields.
- 2026-11-05: Tests copy one database migrated per run instead of migrating each test's database, and use cheap Argon2 parameters; one test still migrates an empty database. Production hashing is unchanged.
- 2026-11-05: Location and notes edits change the spool row directly rather than writing events, because the event types are only the spool's state changes (received, opened, empty, revert). Confirmed by the user.
- 2026-11-05: Rotating a revoked scanner's token re-enables it, since a revoked device ID cannot be registered again. Confirmed by the user.
- 2026-11-05: Manual actions may be backdated but not more than 5 minutes into the future. Accepting a flagged event twice keeps the first review; only flagged events still in effect can be accepted. Only tags with no spool can be dismissed.
- 2026-11-05: npm packages are installed with `--before` a date at least a week back, so no version younger than a week is pulled in (several had been published that day). TypeScript stays on 6.0 because SvelteKit 3.1 and svelte-check require it.
- 2026-11-05: Approved exception (user, AGENTS.md section 5): `deepmerge` 4.3.1, low severity, CVE-2026-93753 / GHSA-gcqx-w48m-w2h4 (https://github.com/advisories/GHSA-gcqx-w48m-w2h4), prototype poisoning when merging attacker-supplied objects. No fixed version exists; it comes in through `@sveltejs/vite-plugin-svelte`, which SvelteKit requires, and only merges our own config at build time. `npm run audit` allows only this advisory at low severity and fails on anything else.
- 2026-11-05: SvelteKit 3 differs from earlier versions: its config goes in `sveltekit({...})` in `vite.config.ts` (no `svelte.config.js`), the library alias is `#lib` (a `package.json` import) instead of `$lib`, and imports name their `.ts` extension.
- 2026-11-05: The web app's CSP allows SvelteKit's one inline bootstrap script by its SHA-256 hash, computed by the server from `index.html` at startup, instead of `'unsafe-inline'`. Unknown paths under `/api` stay JSON 404s rather than the app.
- 2026-11-05: Added the `WEB_DIR` setting (defaults to `web/build` in a checkout) so the Docker image can point at its copy of the build. Server tests point it at a missing folder so they do not depend on a local build.
- 2026-11-05: Web mockups decisions (user): build per-spool % left on Inventory, grams left, the AMS slot strip, Review "Bring back" for Accept and dismiss, a password length meter, role descriptions, and a Light/Dark/System theme choice. The nearly-out cutoff is per product (`nearly_out_pct`, default 15). No backdating field in the UI. Fonts are bundled because the CSP blocks Google Fonts.
- 2026-11-06: On a P1S the AMS reports the tag's tray UID as `tray_uuid`, so spools are matched by tray UID as planned. Its `tag_uid` starts with the tag's 4-byte UID and is not used.
- 2026-11-06: AMS HT units are supported (approved by the owner): unit IDs from 128 with one slot, shown as "AMS HT n". The external spool holder is not read.
- 2026-11-06: The pairing QR code holds `{"v": 1, "url": ..., "token": ...}`, drawn as SVG from the `uqr` module matrix (no HTML strings, so the CSP is unchanged). The server address defaults to the one the admin is using.
- 2026-11-06: `BAMBU_KDF_SALT` is not generated: it is the published key-derivation constant. `ft-sim check-salt` confirms it by re-deriving the keys stored in a dump's sector trailers.
- 2026-11-06: The pairing QR code also holds the device ID (owner's choice over a new `/devices/me` route), because the server refuses a scan whose `device_id` does not match its token.
- 2026-11-06: In the app, Scan and Pairing need no user sign-in (the phone is a scanner, and before pairing there is no server to sign in to); the rest of the web app signs in as usual against the paired server.

## Open questions

- The case model must be adjusted for the speaker that was ordered: a 15 × 10 × 3.5 mm rectangular cavity speaker (8 Ω, JST PH 1.25 mm plug, 80 mm lead) instead of the 20 mm round one in `filament-scanner-case.scad`. Replace the round holder with a rectangular one and resize the grille. Before changing it, check on the real parts which face the sound opening is on and where the CYD's speaker socket is. The lead may need an extension or a splice to reach the socket. Update BOM item 5 at the same time. Due by M4.
- The user will confirm on the real parts and report back: JST connector sizes, the CN1 pinout, CC pull-downs on the USB-C breakout, two-supply protection on the CYD, and whether the CYD's 3.3 V supply can power the PN532.
- `fastapi.testclient` warns that using httpx with Starlette's test client is deprecated and suggests `httpx2`. Tests pass. Vet `httpx2` and get approval before switching.

See also the Open questions section of docs/SPEC.md.
