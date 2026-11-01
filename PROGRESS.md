# Progress

## Done

- Spec and enclosure design committed.
- README.md added, and AGENTS.md now requires keeping it up to date.
- M0a partly done: a Pixel 9 Pro XL running BambuTagScanner read filament tags, including through one box with contents not recorded.
- Spec updated with the approved gap fixes, test tools and milestone order; `nfc_skin` set to 1.0 mm.
- Enclosure manifest renamed to `manifest.json`.
- Server skeleton with a health check, plus CI for lint, tests, the 90% coverage gate and a dependency audit.

## In progress

- `feature/bom`: bill of materials corrected, awaiting user acceptance before push and PR.

## Next

- Finish M0a: compare dumps from two rolls of the same product, retest a labeled box, and scan a refill if available. Dumps stay outside the repo.
- M1 Server core, starting with the decoder and generated tags.

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

## Open questions

- Confirm on the real parts: JST connector sizes, the CN1 pinout, CC pull-downs on the USB-C breakout, two-supply protection on the CYD, and whether the CYD's 3.3 V supply can power the PN532.
- `fastapi.testclient` warns that using httpx with Starlette's test client is deprecated and suggests `httpx2`. Tests pass. Vet `httpx2` and get approval before switching.
- `.env.example` was not added because agent permission settings block writing it. Settings are documented in the spec's Configuration table.

See also the Open questions section of docs/SPEC.md.
