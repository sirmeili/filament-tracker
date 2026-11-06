# Phone app Scan screen mockups

Mockups for the phone app's Scan screen (Phone scanner (Android app) in [docs/SPEC.md](../../SPEC.md); today `web/src/routes/scan/+page.svelte`). They use the same style and tokens as the web mockups: see [../web/README.md](../web/README.md) and [../web/tokens.css](../web/tokens.css).

The live, clickable version is on the owner's Claude design canvas, which also holds the three directions explored first (A: tap target, B: session list, C: color field). These files are the chosen combination: A by default, plus B as an "unpacking a delivery" mode.

## Files

| Mockup | Shows |
| --- | --- |
| [Scan.dc.html](Scan.dc.html) | The interactive screen: one-spool mode, the Delivery toggle and the Light/Dark/System toggle all work |
| [Scan-Unpack-Idle.dc.html](Scan-Unpack-Idle.dc.html) | Unpacking: waiting for the next spool |
| [Scan-Unpack-Found.dc.html](Scan-Unpack-Found.dc.html) | Unpacking: a spool was scanned, choose an action |
| [Scan-Unpack-Done.dc.html](Scan-Unpack-Done.dc.html) | Unpacking: the action was recorded |

The three `Scan-Unpack-*` files are copies of `Scan.dc.html` with a different starting state and their timers off. Read `Scan.dc.html`; the copies are only there to show the states side by side. How to read the `.dc.html` format is in [../web/README.md](../web/README.md#reading-a-dchtml-file). Sample data is fake.

## Layout

The screen is drawn at 390 × 844. Everything you touch while scanning is in the bottom half, so it works with one hand.

**Header:** "Scan", the connection pill (Online, or Offline with the queue count), a Light / Dark / System toggle, and a button to the full app.

**One spool (the default), as in today's flow:**

1. Waiting: a large pulsing target in the middle, "Hold a spool to the back of your phone". At the bottom left is the **Delivery** toggle; beside it, the last scan with Undo (or, before any scan, a hint to turn on unpacking).
2. Spool found: a large ring in the spool's color, the state chip, the name and the state date. At the bottom, a 15-second countdown bar and the three action keys in a row, like the scanner's keys, with the suggested one highlighted and marked "Suggested".
3. Recorded: the ring with a check, the action in large type, the name and spool number. A 3-second bar, then back to waiting. Buttons: Undo, View spool, Scan next.

**Unpacking a delivery** (Delivery toggle pressed):

- The top of the screen is the list of spools scanned in this session, newest at the bottom, nearest the thumb, with a total ("4 new · 0 opened").
- The bottom is one panel that changes with the step: **Ready** (with the Delivery toggle to its left) → **spool found** (ring, state, name, the three keys, countdown) → **recorded** ("Recorded New", Undo, then back to Ready after 3 seconds). The recorded spool is highlighted in the list.
- A spool that is not tracked yet shows "Not tracked yet", and New is suggested.

The Delivery toggle is hidden while a spool is on screen or just recorded, so the keys get the full width and the mode cannot change halfway through a choice.

**States not drawn here:** looking up, sending, an unreadable tag, Info (AMS % left and a link to the spool), Offline (the card decoded on the phone, New / Opened / Empty, the queue count in the header pill) and the NFC problems (no NFC, NFC off, no MIFARE Classic). Draw them in the same layout as the one-spool screens: the message in the middle, actions at the bottom. The canvas has offline and NFC-off examples in the earlier direction A.

## Beyond the spec

The spec covers the one-spool flow. These need the owner's approval and a spec update before they are built:

1. **The unpacking mode** and its **Delivery** toggle. The spec keeps only the last scan; this keeps a list for the session. Only the newest row has Undo, matching the spec's single Undo. Decide whether the list survives leaving the screen, and when a session ends.
2. **View spool and Scan next** on the one-spool result screen. The spec shows the result for 3 seconds and returns to waiting; these are shortcuts during those 3 seconds.
3. **The Light / Dark / System toggle in the Scan header.** The owner asked for it here for now. The web app already has a theme choice; the Scan screen may end up using that instead.
