import { describe, expect, it } from "vitest";
import { navItemFor, requiredRole, visibleNav } from "#lib/nav.ts";

const labels = (role: Parameters<typeof visibleNav>[0]) => visibleNav(role).map((i) => i.label);

describe("visibleNav", () => {
  it("hides admin pages from viewers and editors", () => {
    for (const role of ["viewer", "editor"] as const) {
      expect(labels(role)).toEqual([
        "Inventory",
        "Spools",
        "Products",
        "Review",
        "Activity",
        "Account",
      ]);
    }
  });

  it("shows everything to admins", () => {
    expect(labels("admin")).toContain("Users");
    expect(labels("admin")).toContain("Devices");
  });

  it("shows nothing when signed out", () => {
    expect(labels(null)).toEqual([]);
  });
});

describe("navItemFor", () => {
  it("matches a page and its sub-pages", () => {
    expect(navItemFor("/")?.label).toBe("Inventory");
    expect(navItemFor("/spools")?.label).toBe("Spools");
    expect(navItemFor("/spools/12")?.label).toBe("Spools");
    expect(navItemFor("/users")?.label).toBe("Users");
  });

  it("does not match lookalike paths", () => {
    expect(navItemFor("/spoolsx")).toBeUndefined();
    expect(navItemFor("/nowhere")).toBeUndefined();
  });
});

describe("requiredRole", () => {
  it("is the page's role, or viewer for pages not in the nav", () => {
    expect(requiredRole("/users")).toBe("admin");
    expect(requiredRole("/devices/scanner-1")).toBe("admin");
    expect(requiredRole("/spools/3")).toBe("viewer");
    expect(requiredRole("/nowhere")).toBe("viewer");
  });
});
