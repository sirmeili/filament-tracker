# Phone web app mockups

Mockups for the web app on a phone-sized screen, as the phone app shows it: the bottom bar, the menu, the Account page with the theme choice, and the Inventory page. They follow the style and tokens of the web mockups ([../web/README.md](../web/README.md), [../web/tokens.css](../web/tokens.css)) and the Scan screen mockups ([../mobile-scanner/](../mobile-scanner/README.md)).

**Open [index.html](index.html) in a browser first.** It shows the four screens side by side at phone size, working: search, filters, expanding rows, the menu, the Light / Dark preview switch at the top right. It is built from the four `.dc.html` files below and needs nothing else (fonts load from Google Fonts when online). The `.dc.html` files are the sources; how to read them is in [../web/README.md](../web/README.md#reading-a-dchtml-file). Sample data is fake.

## Files

| Mockup | Shows |
| --- | --- |
| [PhoneInventory-Filter.dc.html](PhoneInventory-Filter.dc.html) | Inventory on a phone: the bottom bar, search and Filter, quick filters, compact rows that expand |
| [PhoneFilterSheet.dc.html](PhoneFilterSheet.dc.html) | The same page with the filter sheet open (PLA and PETG picked) |
| [PhoneMenu.dc.html](PhoneMenu.dc.html) | The menu, opened from the bottom bar |
| [PhoneAccount.dc.html](PhoneAccount.dc.html) | Account, with the Appearance (theme) choice |
| [index.html](index.html) | All four in one page, interactive |

## When this layout applies

On phone-sized screens only (the phone app, or a narrow browser). Tablet and desktop keep today's header with the nav across the top, and Inventory keeps its Cards / List choice there.

## Shell

- **Top:** the RollCall mark and the page title. Nothing else.
- **Bottom bar**, on every page: **Menu** at the far left, a raised round **Scan** button in the center, and the signed-in user (initial and name) at the far right, which opens Account. Scan opens the Scan screen ([../mobile-scanner/](../mobile-scanner/README.md)); in a plain browser, where there is no NFC, it can be left out or kept as a link.
- **Menu:** a sheet that rises from the bottom over a dimmed page. Large buttons in two columns: Inventory, Spools, Products, Review (with its count), Activity; then an **Admin** row of smaller buttons: Devices, Users, Settings. Items the user's role does not allow are hidden. The current page is filled in. The Menu button turns into **Close** while the sheet is open; tapping the dimmed page also closes it.

## Account

- **Appearance:** three large buttons, Light / Dark / System. **Saved per device** (owner, 2026-11-10): each phone and browser keeps its own choice, as the header control does today. The theme control leaves the header (and the Scan screen's header) once it is here.
- **Change password** (opens the existing form), **This phone** (shows Paired, and opens the phone's pairing), then **Sign out**.

## Inventory

From the top:

1. **Search** ("Search name or color") and a **Filter** button on one row. The Filter button turns dark and shows a count while any filter is on.
2. **Quick filters:** "Low stock" and "Nearly out" chips, each with its count in an orange badge. Tapping one shows only those products; tapping again turns it off. When types are picked in the filter sheet, one chip summarises them (see below) with an ✕ to clear it, followed by **Clear**.
3. **The list** (the only layout on a phone, no Cards / List switch):
   - Header row: the count ("All 11" or "5 of 11"), then **Sealed**, **Open** and **Used** with their totals under each heading.
   - Each row: the color ring, the name (up to two lines), then a LOW tag when it applies and the type and color in mono ("PLA · #000000"), then the three counts in fixed columns, and a chevron.
   - **Tapping a row expands it** in place (only one at a time): one bar per open spool with its % left (orange when nearly out, "Not seen by the AMS" when unknown, "None open"), the low-stock rule ("At 2 sealed or fewer" or Off), the status (LOW · ≤2, OK or Alert off), the source (From tag or Added by hand), and **View spools** and **Edit product** buttons.
   - **Only products on hand are listed:** a product with no sealed or open spools does not appear. Its used-up spools stay on Spools, and the product stays on Products.

**Filter sheet** (rises from the bottom):

- **Type:** a chip per filament type you have, with its product count, most common first. Types with nothing on hand are not shown. Several can be picked. Picking every type is the same as picking none.
- **Show:** Low stock only (the same filter as the quick chip).
- **Sort:** Low first, Name, Most stock.
- **Clear** and **Show N products** at the bottom.

The type chip on the page summarises the choice so it never grows: one or two types by name ("PLA, PETG"), "All but ABS" when one is left out, otherwise "5 types". Tapping the chip's label reopens the sheet.

## Spec changes these need

The spec already lists **Phone bottom bar** and **Theme choice in Account** under Future enhancements. These mockups show how they look. The rest is new and needs the owner's approval and a spec update before it is built:

1. **Inventory on a phone:** the compact rows with expanding detail instead of cards, and no Cards / List switch.
2. **Filtering:** search, the filter sheet (several types at once, Low stock only, the three sorts) and the Low stock / Nearly out quick filters, instead of the type chips and the sort button.
3. **Inventory lists only products on hand**, on every screen size. Today it also lists products whose spools are all used up.
4. **This phone** on Account, linking to the phone's pairing.
