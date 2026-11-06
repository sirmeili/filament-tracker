import { describe, expect, it } from "vitest";
import { dayLabel, groupByDay, SOURCE_FILTERS, timeOfDay } from "#lib/activity.ts";
import { ago, deviceId, DEVICE_ID_PATTERN, deviceStatus, seenText } from "#lib/devices.ts";
import { blankIsNull, emptyEntry, entryProblem, rgbaOf } from "#lib/manual-entry.ts";
import {
  isLanHost,
  isLoopbackHost,
  normalizeUrl,
  PAIRING_VERSION,
  pairingPayload,
  qrPath,
  serverUrlError,
} from "#lib/pairing.ts";
import { passwordMeterText, passwordOk, passwordProgress } from "#lib/password.ts";
import { flaggedText, spoolName, tagText } from "#lib/review.ts";
import {
  byAms,
  printerStatus,
  reportText,
  shortFingerprint,
  amsName,
  slotName,
  slotText,
} from "#lib/printers.ts";
import { ROLE_DESCRIPTIONS, ROLES } from "#lib/roles.ts";
import type { DeviceOut, PrinterOut } from "#lib/api/types.ts";
import { event } from "../test/fixtures.ts";

const NOW = new Date(2026, 10, 6, 15, 0); // Nov 6, 3 PM local time

function local(day: number, hour = 12): string {
  return new Date(2026, 10, day, hour, 30).toISOString();
}

function device(overrides: Partial<DeviceOut> = {}): DeviceOut {
  return {
    id: "scanner-1",
    name: "Workbench",
    created_at: local(1),
    last_seen_at: null,
    fw_version: null,
    queue_length: null,
    online: false,
    revoked: false,
    ...overrides,
  };
}

describe("activity", () => {
  it("labels days relative to today", () => {
    expect(dayLabel(local(6), NOW)).toBe("Today");
    expect(dayLabel(local(5), NOW)).toBe("Yesterday");
    expect(dayLabel(local(3), NOW)).toBe("Nov 3");
    expect(dayLabel(new Date().toISOString())).toBe("Today");
  });

  it("groups runs of events by day", () => {
    const events = [
      event({ id: "a", recorded_at: local(6, 9) }),
      event({ id: "b", recorded_at: local(6, 8) }),
      event({ id: "c", recorded_at: local(3) }),
    ];

    const days = groupByDay(events, NOW);

    expect(days.map((d) => [d.label, d.events.map((e) => e.id)])).toEqual([
      ["Today", ["a", "b"]],
      ["Nov 3", ["c"]],
    ]);
    expect(groupByDay([])).toEqual([]);
  });

  it("offers the four source filters and formats times", () => {
    expect(SOURCE_FILTERS.map((f) => f.label)).toEqual(["All", "Scanners", "Web app", "Printer"]);
    expect(timeOfDay(local(6, 9))).toBe("9:30 AM");
  });
});

describe("review wording", () => {
  it("explains each kind of flag", () => {
    expect(flaggedText(event({ type: "empty" })).body).toMatch(/never opened/);
    expect(flaggedText(event({ type: "opened" })).title).toBe("Opened, flagged");
    expect(flaggedText(event({ type: "received" })).body).toMatch(/added by hand/);
    expect(flaggedText(event({ type: "mystery" })).body).toBe("Recorded out of order.");
    expect(spoolName(event({ spool_id: 4 }))).toBe("Black PLA Basic #4");
  });

  it("describes unidentified tags", () => {
    const base = { uid: "AB", first_seen_at: local(3) };
    expect(tagText({ ...base, readable: false, decoded: null }).title).toBe("Unreadable tag");
    expect(
      tagText({ ...base, readable: true, decoded: { detailed_filament_type: "PLA Matte" } }).title,
    ).toBe("Unknown tag (PLA Matte)");
    expect(tagText({ ...base, readable: true, decoded: { filament_type: "PLA" } }).title).toBe(
      "Unknown tag (PLA)",
    );
    expect(tagText({ ...base, readable: true, decoded: null }).title).toBe("Unknown tag");
  });
});

describe("devices", () => {
  it("makes an ID from a name", () => {
    expect(deviceId("Office scanner")).toBe("office-scanner");
    expect(deviceId("  Garage #2 (back) ")).toBe("garage-2-back");
    expect(deviceId("Café")).toBe("cafe");
    expect(deviceId("x".repeat(70) + " y")).toHaveLength(64);
    expect(deviceId("a".repeat(63) + " b")).toBe("a".repeat(63));
    expect(DEVICE_ID_PATTERN.test("office-scanner")).toBe(true);
    expect(DEVICE_ID_PATTERN.test("-office")).toBe(false);
  });

  it("says how long ago a device was seen", () => {
    const at = (minutes: number) => new Date(NOW.getTime() - minutes * 60_000).toISOString();
    expect(ago(at(0), NOW)).toBe("just now");
    expect(ago(at(12), NOW)).toBe("12 min ago");
    expect(ago(at(130), NOW)).toBe("2 h ago");
    expect(ago(local(1), NOW)).toBe("Nov 1");
    expect(ago(new Date().toISOString())).toBe("just now");
    expect(seenText(device(), NOW)).toBe("Never seen");
    expect(seenText(device({ last_seen_at: at(3) }), NOW)).toBe("Last seen 3 min ago");
    expect(seenText(device({ last_seen_at: new Date().toISOString() }))).toBe("Last seen just now");
  });

  it("gives each device a status", () => {
    expect(deviceStatus(device({ online: true }))).toBe("online");
    expect(deviceStatus(device())).toBe("offline");
    expect(deviceStatus(device({ revoked: true, online: true }))).toBe("revoked");
  });
});

describe("passwords", () => {
  it("measures progress to 12 characters", () => {
    expect(passwordProgress("")).toBe(0);
    expect(passwordProgress("abcdef")).toBe(0.5);
    expect(passwordProgress("x".repeat(40))).toBe(1);
    expect(passwordMeterText("")).toBe("At least 12 characters");
    expect(passwordMeterText("x".repeat(11))).toBe("1 more character");
    expect(passwordMeterText("x".repeat(5))).toBe("7 more characters");
    expect(passwordMeterText("x".repeat(12))).toBe("Long enough");
    expect(passwordMeterText("x".repeat(257))).toBe("At most 256 characters");
    expect(passwordOk("x".repeat(12))).toBe(true);
    expect(passwordOk("x".repeat(11))).toBe(false);
    expect(passwordOk("x".repeat(257))).toBe(false);
  });
});

describe("manual entry", () => {
  const entry = emptyEntry();

  it.each([
    [{ choice: "existing", productId: null }, "Choose a product."],
    [{ choice: "existing", productId: 3 }, null],
    [{ choice: "new", name: " " }, "Enter the product's name."],
    [{ choice: "new", name: "x".repeat(101) }, "Names are at most 100 characters."],
    [{ choice: "new", name: "TPU" }, "Enter the filament type, such as PLA."],
    [{ choice: "new", name: "TPU", type: "x".repeat(33) }, "Types are at most 32 characters."],
    [{ choice: "new", name: "TPU", type: "TPU", color: "red" }, "Choose a color."],
    [{ choice: "new", name: "TPU", type: "TPU", color: "#0a0B0c" }, null],
  ] as const)("checks %o", (change, problem) => {
    expect(entryProblem({ ...entry, ...change })).toBe(problem);
  });

  it("converts the color and blank text", () => {
    expect(rgbaOf("#0a0b0c")).toBe("0A0B0CFF");
    expect(blankIsNull("  ")).toBeNull();
    expect(blankIsNull(" Bin 3 ")).toBe("Bin 3");
  });
});

describe("roles", () => {
  it("describes every role", () => {
    expect(ROLES.map((r) => ROLE_DESCRIPTIONS[r].length > 0)).toEqual([true, true, true]);
  });
});

describe("printers", () => {
  const base: PrinterOut = {
    id: 1,
    name: "P1S",
    host: "h",
    port: 8883,
    configured: true,
    connection: "connected",
    online: true,
    last_report_at: null,
    pinned_sha256: null,
    presented_sha256: null,
    slots: [],
  };

  it("names slots from 0-based indexes", () => {
    expect(slotName(0, 1)).toBe("AMS 1, slot 2");
    expect(slotName(128, 0)).toBe("AMS HT 1");
    expect(slotName(129, 0)).toBe("AMS HT 2");
    expect(amsName(3)).toBe("AMS 4");
    expect(amsName(128)).toBe("AMS HT 1");
    expect(slotText({ printer_id: 1, printer_name: "P1S", ams_index: 1, tray_index: 3 })).toBe(
      "AMS 2, slot 4 on P1S",
    );
  });

  it("gives each printer a status", () => {
    expect(printerStatus(base)).toBe("online");
    expect(printerStatus({ ...base, online: false })).toBe("offline");
    expect(printerStatus({ ...base, configured: false })).toBe("not_configured");
    expect(printerStatus({ ...base, connection: "pin_mismatch", configured: false })).toBe(
      "pin_mismatch",
    );
  });

  it("describes the last report and shortens fingerprints", () => {
    expect(reportText(base)).toBe("No report yet");
    expect(reportText({ ...base, last_report_at: local(6, 14) }, NOW)).toBe(
      "Last report 30 min ago",
    );
    expect(reportText({ ...base, last_report_at: new Date().toISOString() })).toBe(
      "Last report just now",
    );
    expect(shortFingerprint("ab12cd34ef56ab78" + "0".repeat(48))).toBe("AB12 CD34 EF56 AB78");
    expect(shortFingerprint("")).toBe("");
  });

  it("groups slots by AMS unit", () => {
    const slots = [
      { ams_index: 1, tray_index: 0 },
      { ams_index: 0, tray_index: 0 },
      { ams_index: 0, tray_index: 1 },
    ];
    expect(byAms(slots).map((g) => [g.ams, g.slots.length])).toEqual([
      [0, 2],
      [1, 1],
    ]);
  });
});

describe("pairing", () => {
  it("accepts http and https addresses only", () => {
    expect(serverUrlError("https://filament.example.com")).toBeNull();
    expect(serverUrlError(" http://192.168.1.20:8000/ ")).toBeNull();
    expect(serverUrlError("filament.example.com")).toMatch(/full address/);
    expect(serverUrlError("ftp://host")).toMatch(/http:\/\/ or https:\/\//);
    expect(serverUrlError("https://me:pw@host")).toMatch(/user name/);
    expect(serverUrlError("https://host/?x=1")).toMatch(/\? or #/);
    expect(serverUrlError("https://host/#a")).toMatch(/\? or #/);
  });

  it("allows plain http only on the home network", () => {
    expect(serverUrlError("http://filament.lan:8000")).toBeNull();
    expect(serverUrlError("http://filament.example.com")).toMatch(/home network/);
    expect(serverUrlError("http://8.8.8.8")).toMatch(/home network/);
    expect(serverUrlError("https://8.8.8.8")).toBeNull();
  });

  it("refuses loopback addresses, which a phone cannot reach", () => {
    for (const url of [
      "http://localhost:8000",
      "https://localhost",
      "http://127.0.0.1:8000",
      "http://[::1]:8000",
      "http://0.0.0.0:8000",
      "http://app.localhost",
    ]) {
      expect(serverUrlError(url)).toMatch(/can't reach localhost/);
    }
    expect(isLoopbackHost("LOCALHOST.")).toBe(true);
    expect(isLoopbackHost("128.0.0.1")).toBe(false);
    expect(isLoopbackHost("localhost.example.com")).toBe(false);
    expect(serverUrlError("http://10.0.0.148:8000")).toBeNull();
  });

  it("knows which hosts are on the home network", () => {
    const lan = [
      "10.1.2.3",
      "127.0.0.1",
      "172.16.0.1",
      "172.31.255.1",
      "192.168.0.10",
      "169.254.1.1",
      "[::1]",
      "[fd12:3456::1]",
      "[fe80::1]",
      "localhost",
      "filament",
      "Filament.Local",
      "nas.lan",
      "box.home.arpa",
      "nas.lan.",
    ];
    const internet = [
      "8.8.8.8",
      "172.15.0.1",
      "172.32.0.1",
      "192.169.0.1",
      "[2001:db8::1]",
      "example.com",
      "lan.example.com",
      "local.example.com",
    ];
    expect(lan.filter((host) => !isLanHost(host))).toEqual([]);
    expect(internet.filter((host) => isLanHost(host))).toEqual([]);
  });

  it("stores the address without a trailing slash", () => {
    expect(normalizeUrl("https://Host.example.com/")).toBe("https://host.example.com");
    expect(normalizeUrl(" http://10.0.0.5:8000/tracker// ")).toBe("http://10.0.0.5:8000/tracker");
  });

  it("puts the version, address and token in the code", () => {
    expect(JSON.parse(pairingPayload("https://host/", "ft_dev_x", "phone-1"))).toEqual({
      v: PAIRING_VERSION,
      url: "https://host",
      token: "ft_dev_x",
      device_id: "phone-1",
    });
  });

  it("draws the code as one path with a border", () => {
    const small = qrPath("hi");
    expect(small.size).toBe(21 + 4); // version 1 plus a 2-module border
    expect(small.path).toMatch(/^(M\d+ \d+h1v1h-1z)+$/);
    expect(small.path).not.toContain("M0 0"); // the border is light
    expect(qrPath("hi")).toEqual(small);
    expect(
      qrPath(pairingPayload("https://host", `ft_dev_${"a".repeat(43)}`, "phone-1")).size,
    ).toBeGreaterThan(small.size);
  });
});
