# Web app mockups

Mockups for the M2 web app pages (Server: web UI in [docs/SPEC.md](../../SPEC.md)), in the chosen style, direction A ("Workshop"). Build the M2 part 6 and 7 pages from these.

The live, clickable version is the Claude design canvas "Filament Tracker — Inventory page style samples", which is private to the owner. It also holds the two rejected directions, B (Ledger) and C (Shelf). They are not copied here.

## What is authoritative

- **The spec wins.** These are pictures of the spec, not changes to it. Anything below under [Beyond the spec](#beyond-the-spec) needs the owner's approval and a spec change before it is built.
- **Layout, hierarchy, copy and tokens** come from the mockups. Match them.
- **Sample data is fake.** Product names, colors, counts, dates, users and devices are made up to fill the screens. Swatch colors approximate Bambu's and were not read from real tags.

## Pages

| Mockup | Route | Spec page | Minimum role |
| --- | --- | --- | --- |
| [Inventory.dc.html](Inventory.dc.html) | `/` | Inventory | Viewer |
| [Spools.dc.html](Spools.dc.html) | `/spools` | Spools | Viewer (edits: Editor) |
| [SpoolDetail.dc.html](SpoolDetail.dc.html) | `/spools/{id}` | Spool detail | Viewer (actions, undo, edits: Editor) |
| [Products.dc.html](Products.dc.html) | `/products` | Products | Viewer (edits: Editor) |
| [Review.dc.html](Review.dc.html) | `/review` | Review | Viewer (resolve: Editor) |
| [Activity.dc.html](Activity.dc.html) | `/activity` | Activity | Viewer (undo: Editor) |
| [Devices.dc.html](Devices.dc.html) | `/devices` | Devices | Admin |
| [Users.dc.html](Users.dc.html) | `/users` | Users | Admin |
| [Account.dc.html](Account.dc.html) | `/account` | Account | Viewer |
| [SignIn.dc.html](SignIn.dc.html) | `/login` | Sign in | None |

The routes are the ones already in `web/src/lib/nav.ts`. The mockups are drawn for an Admin, so every control is visible. Hide the controls a role does not allow, as the spec says.

One layout difference from the current nav: the mockups take Account out of the nav links and reach it from the account button (initial and username) at the right of the header.

## Reading a `.dc.html` file

Each file is one page: plain HTML and CSS, plus a small template layer. The files need the design canvas runtime (`support.js`) to render, so opening them straight from disk shows the raw template. Read them as source:

- `<helmet><style>` holds the page CSS. The `.light` / `.dark` blocks are the tokens, also collected in [tokens.css](tokens.css).
- `{{name}}` inserts a value from `renderVals()` in the `<script type="text/x-dc">` block at the bottom.
- `<sc-for list="{{items}}" as="p">` repeats its contents for each item; `<sc-if value="{{cond}}">` shows its contents when the value is true.
- `renderVals()` holds the sample data and the interaction logic (filters, sort, selection, undo). Treat it as behavior notes, not code to port.
- `href="Spools.dc.html"` links stand for routes in the table above.

## Design rules

- **Theme:** light and dark, with a toggle in the header (sun/moon icon button). Tokens are in [tokens.css](tokens.css). `web/src/app.css` already has base light and dark CSS; replace its values with these tokens in part 6.
- **Type:** Space Grotesk for headings and product names, Inter for body text, JetBrains Mono for counts, percentages, color hex, IDs and dates.
- **Header:** logo and name, the nav as pill links (active = filled with `--text`), Review with a count badge in `--accent`, then the theme toggle and an account button. It wraps on narrow screens.
- **Spool swatch:** a ring (thick border in the tag's RGBA color, hole in `--bg`), drawn the same way for every color. Light mode uses a drop shadow outside and a small inner shadow in the hole. Dark mode uses a gap in the surface color, a thin light rim and a soft glow, both outside and around the hole. Small rings in tables (`.ring.sm`) use thinner lines in dark mode. The aim is for white to stay visible on light cards and black on dark ones.
- **State chips:** Sealed = filled with `--text`; Open = `--chip` with a border; Used up = dashed outline in `--muted`. Labels are uppercase. The UI says "Used up" for the `empty` state.
- **Low stock / flagged:** `--lowbg` with `--lowtext`.
- **% left bars:** an 8 px bar on `--track`, filled with `--fill` or, below the nearly-out cutoff, `--fillLow`, with the number in mono beside it. When the AMS has not reported an open spool, show "Not seen by the AMS" instead of a bar.
- **Touch targets** are at least 44 px; buttons and filters are real `<button>` elements; tables sit in a horizontally scrolling box on phones.
- **Inventory** has a Cards / List switch. Cards show the three counts and one bar per open spool; List is the same data as a table.

## Beyond the spec

The mockups show these, but the spec does not cover them yet. Do not build them until the owner approves them and the spec is updated:

1. **Inventory: % left for each open spool**, on cards and in the list, and an "Open, under 15%" summary tile. `GET /inventory` returns only counts; this needs each open spool's `remaining_pct` in `ProductSummary` (or a second call to `/spools`).
2. **The 15% "nearly out" cutoff**: fixed, a setting, or dropped. It may share a rule with the M5 "likely empty" suggestions.
3. **Spool detail: grams left** worked out from the AMS % and the tag's weight.
4. **Spool detail: a backdating field** for manual actions. The write API already accepts a past time; the spec does not say the UI exposes it.
5. **Review: a "Bring back" banner** after resolving an item.
6. **Account: a password length meter.**
7. **Devices: the AMS slot strip** on the printer card.
8. **Users: a short description of each role** under the table.
