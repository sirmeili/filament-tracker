// Filament Tracker scanner case
// Wall-mounted enclosure for an ESP32 "Cheap Yellow Display" (ESP32-2432S028R),
// a PN532 NFC module, three soft-key buttons, a small speaker and a USB-C power input.
// Coordinates: Z up, front faces -Y, back (wall side) at +Y. Units: mm.
// Mount by keyhole screws, magnets (4 x 10x3 discs) or Command strips on the flat back.

/* [Case] */
case_w = 112;        // [100:1:140]
case_h = 166;        // [150:1:200]
case_d = 26;         // [22:1:40]
wall = 2.5;          // [2:0.5:4]
front_t = 2.0;       // [1.6:0.2:3]
corner_r = 6;        // [2:1:10]
back_t = 4;          // [3:0.5:6]
fit = 0.3;           // [0.1:0.05:0.6] clearance between back plate and shell

/* [Layout] */
screen_z = 81;       // [70:1:100] centre of the screen window
button_z = 38;       // [30:1:50] centre of the button row
button_pitch = 21;   // [16:1:30] spacing between the three buttons
nfc_z = 139;         // [125:1:150] centre of the NFC tap zone
speaker_z = 16;      // [12:1:24]
usbc_x = -32;        // [-45:1:45] USB-C power input position along the bottom

/* [Screen window] */
view_w = 57.6;       // [50:0.1:65] visible area of the 2.8" TFT
view_h = 43.2;       // [38:0.1:50]
window_offset_x = 0; // [-6:0.1:6] shift if your panel's visible area is off-centre
bezel_chamfer = 1.5; // [0:0.25:3]

/* [NFC tap zone] */
nfc_skin = 1.2;      // [0.8:0.2:1.6] plastic left over the PN532 antenna
tap_ring_d = 34;     // [24:1:40]
tap_ring_w = 1.6;    // [0.8:0.2:3]
tap_ring_depth = 0.4;// [0.2:0.2:0.8] inlay depth (print in a second colour with the AMS)

/* [Buttons] */
cap_d = 12;          // [10:0.5:14]
cap_proud = 1.5;     // [0:0.5:3] how far the caps stand out of the front

/* [Wall mount] */
keyholes = true;
keyhole_x = 35;      // [20:1:45]
keyhole_z = 128;     // [100:1:145]
screw_head_d = 9;    // [7:0.5:11]
screw_shank_d = 4.5; // [3:0.5:6]
magnets = true;
magnet_d = 10.2;     // [6:0.1:15] pocket diameter (10 mm magnets + 0.2)
magnet_t = 3.2;      // [2:0.1:5]  pocket depth (3 mm magnets + 0.2)
magnet_x = 38;       // [20:1:48]
magnet_z1 = 20;      // [12:1:40]
magnet_z2 = 150;     // [120:1:155]

/* [Render] */
part = "all"; // [all, front, back, inlay, caps, cyd_pcb, cyd_screen, cyd_parts, pn532_pcb, pn532_parts, button_board, switches, speaker, usbc_board, usbc_port, magnets, inserts]
$fn = 48;

// ---------- derived ----------
inner_w = case_w - 2 * wall;
inner_h = case_h - 2 * wall;
inner_r = max(corner_r - wall, 0.5);
cavity_back = case_d - back_t;          // inner face of the back plate

// CYD (ESP32-2432S028R): 86 x 50 PCB, 69.2 x 50 TFT module on the front
cyd_pcb_w = 86; cyd_pcb_h = 50; cyd_pcb_t = 1.6;
tft_w = 69.2; tft_h = 50; tft_t = 3.9;
tft_x0 = window_offset_x - tft_w / 2;   // TFT left edge (visible area centred on window)
cyd_x0 = tft_x0;                        // PCB shares the TFT's left edge; extra length runs right
tft_y0 = front_t;
cyd_y0 = tft_y0 + tft_t;                // PCB front face
cyd_y1 = cyd_y0 + cyd_pcb_t;            // PCB back face

// PN532 V3 module: 42.7 x 40.4
pn_w = 42.7; pn_h = 40.4; pn_t = 1.6;
pn_y0 = nfc_skin;

// Buttons: 12 x 12 x 7.3 tact switches on a 70 x 18 perfboard strip
sw_body = 12; sw_body_t = 3.5;
cap_y0 = -cap_proud; cap_len = 6;
sw_y0 = cap_y0 + cap_len;               // switch body front face
bb_w = 70; bb_h = 18; bb_t = 1.6;
bb_y0 = sw_y0 + sw_body_t;

// Speaker: 20 mm round, 4 mm deep
spk_d = 20; spk_t = 4;

// USB-C breakout, receptacle facing down through the bottom wall
usbc_y = 14;
uc_w = 8.94; uc_t = 3.26; uc_l = 7.35;

boss_d = 8;
// bosses sink 0.5 mm into the walls so they fuse cleanly (no tangent edges)
boss_pos = [for (sx = [-1, 1], z = [wall + 3.5, case_h - wall - 3.5]) [sx * (inner_w / 2 - 3.5), z]];

// ---------- helpers ----------
// Rounded rectangle in XZ, extruded along +Y from y0 to y1, centred on x = 0, z = cz.
module rprism(w, h, r, y0, y1, cz) {
    hull() for (sx = [-1, 1], sz = [-1, 1])
        translate([sx * (w / 2 - r), y0, cz + sz * (h / 2 - r)])
            rotate([-90, 0, 0]) cylinder(r = r, h = y1 - y0);
}
// Cylinder along +Y starting at (x, y0, z)
module ycyl(x, y0, z, d, len, fn = 0) {
    translate([x, y0, z]) rotate([-90, 0, 0]) cylinder(d = d, h = len, $fn = fn > 0 ? fn : $fn);
}
// Box from corner (x0, y0, z0) with size
module boxat(x0, y0, z0, w, t, h) { translate([x0, y0, z0]) cube([w, t, h]); }

// ---------- front shell ----------
module front_shell() {
    difference() {
        union() {
            difference() {
                rprism(case_w, case_h, corner_r, 0, case_d, case_h / 2);
                rprism(inner_w, inner_h, inner_r, front_t, case_d + 1, case_h / 2);
            }
            // screw bosses for M3 heat-set inserts
            for (p = boss_pos) ycyl(p[0], front_t - 0.01, p[1], boss_d, cavity_back - front_t + 0.01);
            // TFT locating frame
            difference() {
                boxat(tft_x0 - 1.6, front_t - 0.01, screen_z - tft_h / 2 - 1.6, tft_w + 3.2, 3, tft_h + 3.2);
                boxat(tft_x0 - 0.4, front_t - 1, screen_z - tft_h / 2 - 0.4, tft_w + 0.8, 5, tft_h + 0.8);
            }
            // button board standoffs
            for (sx = [-1, 1]) ycyl(sx * (bb_w / 2 - 3), front_t - 0.01, button_z, 5, bb_y0 - front_t + 0.01);
            // speaker holder ring
            difference() {
                ycyl(0, front_t - 0.01, speaker_z, spk_d + 4.6, spk_t + 1);
                ycyl(0, front_t - 1, speaker_z, spk_d + 0.6, spk_t + 3);
            }
            // USB-C board backstop
            boxat(usbc_x - 7, usbc_y + uc_t / 2 + 1.7, wall - 0.01, 14, 2, 12);
        }
        // screen window with outward chamfer
        hull() {
            boxat(window_offset_x - (view_w + 1) / 2, front_t - 0.2, screen_z - (view_h + 1) / 2, view_w + 1, 0.4, view_h + 1);
            boxat(window_offset_x - (view_w + 1) / 2 - bezel_chamfer, -0.2, screen_z - (view_h + 1) / 2 - bezel_chamfer,
                  view_w + 1 + 2 * bezel_chamfer, 0.21, view_h + 1 + 2 * bezel_chamfer);
        }
        // thin skin over the PN532 antenna (pocket also locates the module)
        boxat(-(pn_w + 0.8) / 2, nfc_skin, nfc_z - (pn_h + 0.8) / 2, pn_w + 0.8, front_t, pn_h + 0.8);
        // tap-zone ring groove (filled by the inlay part)
        tap_ring(0.01);
        // button holes
        for (i = [-1:1]) ycyl(i * button_pitch, -1, button_z, cap_d + 0.8, front_t + 2);
        // speaker grille
        grille();
        // USB-C opening in the bottom wall
        translate([usbc_x, usbc_y, -1]) hull() for (sx = [-1, 1])
            translate([sx * (9.6 - 3.9) / 2, 0, 0]) cylinder(d = 3.9, h = wall + 2, $fn = 24);
        // service slot in the right wall for the CYD's own USB port (flashing)
        boxat(case_w / 2 - wall - 1, cyd_y1 - 2.5, screen_z - 6, wall + 2, 8, 12);
        // insert holes
        for (p = boss_pos) ycyl(p[0], cavity_back - 6, p[1], 4.0, 7, 24);
    }
}

module tap_ring(extra) {
    translate([0, -0.01, nfc_z]) rotate([-90, 0, 0]) difference() {
        cylinder(d = tap_ring_d + extra, h = tap_ring_depth + 0.01);
        translate([0, 0, -1]) cylinder(d = tap_ring_d - 2 * tap_ring_w - extra, h = tap_ring_depth + 2);
    }
}

module grille() {
    pts = concat([[0, 0]],
                 [for (a = [0:60:359]) [4.5 * cos(a), 4.5 * sin(a)]],
                 [for (a = [15:30:359]) [8 * cos(a), 8 * sin(a)]]);
    for (p = pts) ycyl(p[0], -1, speaker_z + p[1], 1.8, front_t + 2, 16);
}

// ---------- back plate (wall side) ----------
module back_plate() {
    difference() {
        union() {
            rprism(inner_w - 2 * fit, inner_h - 2 * fit, max(inner_r - fit, 0.5), cavity_back, case_d, case_h / 2);
            // posts pressing the CYD PCB against the front
            for (x = [cyd_x0 + 3.5, cyd_x0 + cyd_pcb_w - 3.5], dz = [-1, 1])
                ycyl(x, cyd_y1 + 0.2, screen_z + dz * (cyd_pcb_h / 2 - 3.5), 5, cavity_back - cyd_y1 - 0.2 + 0.01);
            // posts holding the PN532 in its pocket
            for (sx = [-1, 1], dz = [-1, 1])
                ycyl(sx * (pn_w / 2 - 3.5), pn_y0 + pn_t + 0.2, nfc_z + dz * (pn_h / 2 - 3.5), 5, cavity_back - pn_y0 - pn_t - 0.2 + 0.01);
        }
        // countersunk M3 holes
        for (p = boss_pos) {
            ycyl(p[0], cavity_back - 1, p[1], 3.4, back_t + 2, 24);
            translate([p[0], case_d - 1.8, p[1]]) rotate([-90, 0, 0]) cylinder(d1 = 3.4, d2 = 6.8, h = 1.81, $fn = 24);
        }
        // keyholes: head enters the round hole and slides down onto the narrow slot
        if (keyholes) for (sx = [-1, 1]) {
            x = sx * keyhole_x;
            // wall layer: entry hole + shank slot
            translate([x, case_d - 2.01, 0]) rotate([-90, 0, 0]) {
                translate([0, -keyhole_z, 0]) cylinder(d = screw_head_d, h = 2.1);
                hull() for (dz = [0, 9]) translate([0, -(keyhole_z + dz), 0]) cylinder(d = screw_shank_d, h = 2.1);
            }
            // inner layer: channel for the screw head
            translate([x, cavity_back - 0.01, 0]) rotate([-90, 0, 0])
                hull() for (dz = [0, 9]) translate([0, -(keyhole_z + dz), 0]) cylinder(d = screw_head_d, h = back_t - 2 + 0.02);
        }
        // magnet pockets, open to the wall face
        if (magnets) for (sx = [-1, 1], z = [magnet_z1, magnet_z2])
            ycyl(sx * magnet_x, case_d - magnet_t, z, magnet_d, magnet_t + 1);
    }
}

// ---------- printed extras ----------
module inlay() { tap_ring(-0.2); }

module caps() {
    for (i = [-1:1]) {
        difference() {
            union() {
                ycyl(i * button_pitch, cap_y0, button_z, cap_d, cap_len);
                ycyl(i * button_pitch, front_t + 0.3, button_z, cap_d + 3, 1.0);
            }
            // socket for the switch's 3.8 mm square stem
            boxat(i * button_pitch - 2.0, sw_y0 - 1.2, button_z - 2.0, 4.0, 1.21, 4.0);
        }
    }
}

// ---------- hardware representations ----------
module cyd_pcb() { boxat(cyd_x0, cyd_y0, screen_z - cyd_pcb_h / 2, cyd_pcb_w, cyd_pcb_t, cyd_pcb_h); }
module cyd_screen() { boxat(tft_x0, tft_y0, screen_z - tft_h / 2, tft_w, tft_t, tft_h); }
module cyd_parts() {
    // ESP32-WROOM module (shield can)
    boxat(cyd_x0 + 30, cyd_y1, screen_z - 9, 25.5, 3.1, 18);
    // micro-USB on the right edge
    boxat(cyd_x0 + cyd_pcb_w - 7, cyd_y1, screen_z - 4, 8, 3, 8);
    // JST connectors (P1 power, P3, CN1 for the PN532, speaker)
    for (z = [-18, -8, 8, 18]) boxat(cyd_x0 + 64, cyd_y1, screen_z + z - 2.5, 6, 4.5, 5);
    // SD card slot
    boxat(cyd_x0 + 4, cyd_y1, screen_z - 7, 15, 1.9, 14);
}
module pn532_pcb() { boxat(-pn_w / 2, pn_y0, nfc_z - pn_h / 2, pn_w, pn_t, pn_h); }
module pn532_parts() {
    boxat(-3.5, pn_y0 + pn_t, nfc_z + 4, 7, 0.9, 7);                       // PN532 chip
    boxat(-10.2, pn_y0 + pn_t, nfc_z - pn_h / 2 + 1, 20.4, 2.5, 2.5);     // header plastic
    for (i = [0:7]) boxat(-9.2 + i * 2.54, pn_y0 + pn_t, nfc_z - pn_h / 2 + 2, 0.64, 9, 0.64); // pins
}
module button_board() {
    difference() {
        boxat(-bb_w / 2, bb_y0, button_z - bb_h / 2, bb_w, bb_t, bb_h);
        for (sx = [-1, 1]) ycyl(sx * (bb_w / 2 - 3), bb_y0 - 1, button_z, 2.2, bb_t + 2, 16);
    }
}
module switches() {
    for (i = [-1:1]) {
        boxat(i * button_pitch - sw_body / 2, sw_y0, button_z - sw_body / 2, sw_body, sw_body_t, sw_body);
        boxat(i * button_pitch - 1.9, sw_y0 - 0.6, button_z - 1.9, 3.8, 0.61, 3.8);
    }
}
module speaker() {
    ycyl(0, front_t + 0.5, speaker_z, spk_d, spk_t);
}
module usbc_board() { boxat(usbc_x - 7, usbc_y + uc_t / 2, wall + 0.2, 14, 1.6, 18); }
module usbc_port() {
    translate([usbc_x, usbc_y, wall - 1.5]) hull() for (sx = [-1, 1])
        translate([sx * (uc_w - uc_t) / 2, 0, 0]) cylinder(d = uc_t, h = uc_l, $fn = 24);
}
module magnets_hw() {
    if (magnets) for (sx = [-1, 1], z = [magnet_z1, magnet_z2])
        ycyl(sx * magnet_x, case_d - 3, z, 10, 3);
}
module inserts() { for (p = boss_pos) ycyl(p[0], cavity_back - 5.7, p[1], 4.6, 5.7, 24); }

// ---------- part selector ----------
if (part == "all" || part == "front") front_shell();
if (part == "all" || part == "back") back_plate();
if (part == "all" || part == "inlay") inlay();
if (part == "all" || part == "caps") caps();
if (part == "all" || part == "cyd_pcb") cyd_pcb();
if (part == "all" || part == "cyd_screen") cyd_screen();
if (part == "all" || part == "cyd_parts") cyd_parts();
if (part == "all" || part == "pn532_pcb") pn532_pcb();
if (part == "all" || part == "pn532_parts") pn532_parts();
if (part == "all" || part == "button_board") button_board();
if (part == "all" || part == "switches") switches();
if (part == "all" || part == "speaker") speaker();
if (part == "all" || part == "usbc_board") usbc_board();
if (part == "all" || part == "usbc_port") usbc_port();
if (part == "all" || part == "magnets") magnets_hw();
if (part == "all" || part == "inserts") inserts();
