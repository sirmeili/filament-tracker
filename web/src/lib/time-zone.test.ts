import { afterEach, describe, expect, it, vi } from "vitest";
import { dayLabel, groupByDay, timeOfDay } from "#lib/activity.ts";
import { api } from "#lib/api/client.ts";
import type { EventOut } from "#lib/api/types.ts";
import { Session } from "#lib/auth/session.svelte.ts";
import {
  calendarDay,
  clockTime,
  currentTimeZone,
  dateTime,
  setTimeZone,
  shortDate,
} from "#lib/format.ts";
import { timeZoneNames } from "#lib/settings-fields.ts";

vi.mock("#lib/api/client.ts", async (original) => ({
  ...(await original<typeof import("#lib/api/client.ts")>()),
  api: vi.fn(),
}));

afterEach(() => setTimeZone(undefined));

// 03:30 UTC on Nov 9 is still Nov 8 in Chicago and already Nov 9 in Berlin.
const LATE = "2026-11-09T03:30:00Z";

describe("the server's time zone", () => {
  it("shows times and days in the chosen zone, whatever the device uses", () => {
    setTimeZone("America/Chicago");
    expect(currentTimeZone()).toBe("America/Chicago");
    expect(clockTime(new Date(LATE))).toBe("9:30 PM");
    expect(calendarDay(new Date(LATE))).toBe("2026-11-08");
    expect(shortDate(LATE, new Date("2026-11-10T12:00:00Z"))).toBe("Nov 8");
    expect(dateTime(LATE, new Date("2026-11-10T12:00:00Z"))).toBe("Nov 8, 9:30 PM");

    setTimeZone("Europe/Berlin");
    expect(clockTime(new Date(LATE))).toBe("4:30 AM");
    expect(calendarDay(new Date(LATE))).toBe("2026-11-09");
  });

  it("compares years in the zone", () => {
    setTimeZone("America/Chicago");
    // Jan 1 03:00 UTC is still Dec 31 of the previous year in Chicago.
    const now = new Date("2027-01-01T03:00:00Z");
    expect(shortDate("2026-12-31T20:00:00Z", now)).toBe("Dec 31");
    expect(shortDate("2025-12-31T20:00:00Z", now)).toBe("Dec 31, 2025");
  });

  it("falls back to the device's zone for none or an unknown name", () => {
    setTimeZone("Mars/Olympus");
    expect(currentTimeZone()).toBeUndefined();
    setTimeZone(null);
    expect(currentTimeZone()).toBeUndefined();
    expect(clockTime(new Date(LATE))).toMatch(/^\d{1,2}:30 [AP]M$/);
  });

  it("labels Today and Yesterday by the zone's calendar", () => {
    setTimeZone("America/Chicago");
    const now = new Date("2026-11-09T15:00:00Z"); // 9 AM Nov 9 in Chicago
    expect(dayLabel("2026-11-09T14:00:00Z", now)).toBe("Today");
    expect(dayLabel(LATE, now)).toBe("Yesterday"); // Nov 8 in Chicago
    expect(dayLabel("2026-11-08T03:00:00Z", now)).toBe("Nov 7");
    expect(timeOfDay(LATE)).toBe("9:30 PM");
    const events = [
      { recorded_at: "2026-11-09T14:00:00Z" },
      { recorded_at: LATE },
      { recorded_at: "2026-11-09T01:00:00Z" },
    ] as EventOut[];
    expect(groupByDay(events, now).map((d) => [d.label, d.events.length])).toEqual([
      ["Today", 1],
      ["Yesterday", 2],
    ]);
  });

  it("a month boundary still finds Yesterday", () => {
    setTimeZone("UTC");
    expect(dayLabel("2026-11-30T10:00:00Z", new Date("2026-12-01T10:00:00Z"))).toBe("Yesterday");
  });

  it("comes from the signed-in user", async () => {
    vi.mocked(api).mockResolvedValueOnce({
      id: 1,
      username: "alice",
      role: "viewer",
      time_zone: "Asia/Tokyo",
    });
    const session = new Session();
    await session.load();
    expect(currentTimeZone()).toBe("Asia/Tokyo");
    session.user = null;
    expect(currentTimeZone()).toBe("Asia/Tokyo"); // signing out keeps the last zone
  });
});

describe("timeZoneNames", () => {
  it("puts UTC first, once", () => {
    expect(timeZoneNames(() => ["Europe/Berlin", "UTC", "America/Chicago"])).toEqual([
      "UTC",
      "Europe/Berlin",
      "America/Chicago",
    ]);
  });

  it("works where the browser cannot list zones", () => {
    expect(timeZoneNames(null)).toEqual(["UTC"]);
  });
});
