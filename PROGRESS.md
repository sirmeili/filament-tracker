# Progress

## Done

- Spec and enclosure design committed.
- README.md added, and AGENTS.md now requires keeping it up to date.

## In progress

- `feature/readme`: awaiting user acceptance before push and PR.

## Next

- M0 Prove reading (docs/SPEC.md, Milestones), then M1 Server core.

## Decisions

- 2026-10-31: Branches use the `feature/...` naming from AGENTS.md, because project rules win over the global `feat/...` convention.
- 2026-10-31: The README mockup link uses the OpenSCAD edition of the viewer, because the manifest has only `.scad` parts and the repo has no STLs.

## Open questions

Spec gaps to settle before the affected work starts:

- `/events/{id}/revert` lists Scanner as a caller, but device tokens are scoped to `/scans` and `/devices/heartbeat`.
- Devices can fetch the key-derivation constant from the server, but no endpoint is defined and the same token scope applies.
- `unidentified` tags: the state is not in the transition table, and `spool.tray_uid` has no value when a tag is unreadable.
- Opened on an empty spool is UI only in the transition table, but the offline scanner offers it and the rules accept out-of-order actions.
- AMS-only spools report type and color, but `product` is keyed on material and variant IDs.
- Enclosure: `nfc_skin` defaults to 1.2 mm in the SCAD model, but the spec requires 1 mm or less over the antenna.
- Enclosure: the SCAD model describes a wall mount, but the spec places the scanner on a shelf.
- The spec expects a repo `CLAUDE.md`, which does not exist yet.
- `hardware/enclosure/mainfest.json` looks like a typo for `manifest.json`. The README mockup link uses this spelling, so a rename must update it.

See also the Open questions section of docs/SPEC.md.
