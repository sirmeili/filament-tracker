# Filament Scanner — Bill of Materials

Per scanner unit, matching the Filament Tracker spec (CYD prototype) and `filament-scanner-case.scad`.
Prices are approximate USD as of 2026-10-31. "Sourced" prices come from the linked page; "Est." prices are typical marketplace prices, so check before ordering.

## Required parts

| # | Category | Item | Spec / notes | Qty | Unit price | Line total | Price basis |
|---|---|---|---|---|---|---|---|
| 1 | Electronics | ESP32 "Cheap Yellow Display" | ESP32-2432S028R, 2.8" 320×240 resistive touch. Prefer the original micro-USB / ILI9341 revision (see notes) | 1 | $12.00 | $12.00 | Sourced, range $8–15 ([atomic14](https://www.atomic14.com/esp32/boards/esp32-2432s028r/)) |
| 2 | Electronics | PN532 NFC module V3 | 42.7 × 40.4 mm, I2C mode (DIP switch), must support MIFARE Classic auth | 1 | $7.00 | $7.00 | Est. |
| 3 | Electronics | Tactile switches | 12 × 12 × 7.3 mm, through-hole | 3 | $0.20 | $0.60 | Est. (pack of 25 ≈ $5) |
| 4 | Electronics | Perfboard strip | Cut 70 × 18 mm from a 50 × 70 mm board, 1.6 mm thick | 1 | $0.50 | $0.50 | Est. |
| 5 | Electronics | Speaker | 20 mm round, 8 Ω, ≤ 4 mm deep, JST 1.25 mm 2-pin lead for the CYD speaker connector | 1 | $2.00 | $2.00 | Est. |
| 6 | Electronics | USB-C breakout (power in) | Must have 5.1 kΩ CC pull-downs so C-to-C chargers supply power, e.g. SparkFun BOB-15100 (22.1 × 14 mm) | 1 | $4.95 | $4.95 | Sourced ([SparkFun](https://www.sparkfun.com/sparkfun-usb-c-breakout.html)) |
| 7 | Electronics | JST 1.25 mm 4-pin cables | One for PN532 (I2C on CN1), one for 5 V power into P1. The CYD often ships with one | 2 | $1.00 | $2.00 | Est. |
| 8 | Electronics | Resistors for button ladder | 1 × 10 kΩ pull-up, 1 × 3.3 kΩ, 1 × 10 kΩ (1/4 W) | 3 | $0.03 | $0.10 | Est. |
| 9 | Electronics | Hookup wire | 26 AWG silicone, a few colors | 1 | $0.50 | $0.50 | Est. |
| 10 | Hardware | M3 heat-set inserts | M3 × 5.7 mm, for 4.0 mm holes in the bosses | 4 | $0.10 | $0.40 | Est. |
| 11 | Hardware | M3 × 8 countersunk screws | Close the back plate | 4 | $0.10 | $0.40 | Est. |
| 12 | Hardware | M2 × 6 self-tapping screws | Button board to standoffs | 2 | $0.10 | $0.20 | Est. |
| 13 | Printed | Front shell, back plate, button caps | PLA or PETG, ~120 g total at 4 walls / 15% infill | 1 | $2.40 | $2.40 | Est. ($20/kg) |
| 14 | Printed | Tap-zone ring inlay | Second color via the AMS, under 1 g | 1 | $0.00 | $0.00 | — |
| | | | | | **Required subtotal** | **$33.05** | |

## Optional (wall mounting, pick one)

| # | Item | Spec / notes | Qty | Unit price | Line total | Price basis |
|---|---|---|---|---|---|---|
| 15 | Neodymium disc magnets | 10 × 3 mm, N52, glued into the back-plate pockets | 4 | $0.25 | $1.00 | Est. |
| 16 | Wall screws + anchors | Pan head, head ≤ 8.5 mm, shank ≤ 4.5 mm (e.g. #6) for the keyholes | 2 | $0.25 | $0.50 | Est. |
| 17 | Command strips | Medium size, on the flat back face | 2 | $0.50 | $1.00 | Est. |
| | | | | **Optional, all three** | **$2.50** | |

**Total per unit: about $33 required, $35.55 with every mounting option.** This is slightly over the spec's $30 target; the CYD price drives most of the difference (about $29 at its low end).

## Notes

- **CYD revision.** The original micro-USB board uses the ILI9341 driver. The two-USB "CYD2USB" revision uses ST7789 (needs display inversion), and its USB-C port has no CC resistors, so C-to-C cables won't power it. Either works because power comes through the separate USB-C breakout, but the firmware must match the display driver.
- **Button ladder.** 10 kΩ pull-up from 3.3 V to GPIO35. Each button connects GPIO35 to GND through 0 Ω, 3.3 kΩ or 10 kΩ, giving about 0 V, 0.82 V and 1.65 V when pressed, and 3.3 V idle.
- **Power wiring.** USB-C breakout VBUS and GND go to the CYD's P1 connector (5 V). The CYD's own USB port stays free for flashing through the side slot.
- **Fit checks.**
    - The SparkFun breakout is 22.1 mm long; the case leaves room above it.
    - The button-board standoffs are printed solid, so drill a 1.6 mm pilot hole for the M2 screws.
    - Confirm the PN532 reads through 1.2 mm of your filament before final assembly.
- **Not included.** Spare NFC tags, the USB-C power supply and cable, and tools (soldering iron, insert tip).