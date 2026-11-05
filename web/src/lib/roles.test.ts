import { describe, expect, it } from "vitest";
import { allows, ROLE_LABELS } from "#lib/roles.ts";

describe("allows", () => {
  it("ranks viewer < editor < admin", () => {
    expect(allows("viewer", "viewer")).toBe(true);
    expect(allows("viewer", "editor")).toBe(false);
    expect(allows("editor", "viewer")).toBe(true);
    expect(allows("editor", "admin")).toBe(false);
    expect(allows("admin", "editor")).toBe(true);
  });

  it("refuses when nobody is signed in", () => {
    expect(allows(null, "viewer")).toBe(false);
    expect(allows(undefined, "viewer")).toBe(false);
  });

  it("has a label for every role", () => {
    expect(Object.values(ROLE_LABELS)).toEqual(["Viewer", "Editor", "Admin"]);
  });
});
