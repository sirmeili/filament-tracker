import { describe, expect, it } from "vitest";
import { guardRedirect, loginUrl, safeNext } from "#lib/auth/redirect.ts";
import type { Me } from "#lib/api/types.ts";

const ALICE: Me = { id: 1, username: "alice", role: "viewer" };

describe("safeNext", () => {
  it.each([
    ["/spools?state=open", "/spools?state=open"],
    ["/", "/"],
    [null, "/"],
    ["", "/"],
    ["https://evil.example", "/"],
    ["//evil.example", "/"],
    ["/\\evil.example", "/"],
    ["javascript:alert(1)", "/"],
    ["/login", "/"],
    ["/login?next=/x", "/"],
  ])("%s -> %s", (next, expected) => {
    expect(safeNext(next)).toBe(expected);
  });
});

describe("loginUrl", () => {
  it("remembers where the user was going", () => {
    expect(loginUrl("/spools", "?state=open")).toBe("/login?next=%2Fspools%3Fstate%3Dopen");
  });

  it("leaves out the home page", () => {
    expect(loginUrl("/", "")).toBe("/login");
  });

  it("marks an ended session", () => {
    expect(loginUrl("/", "", true)).toBe("/login?expired=1");
  });
});

describe("guardRedirect", () => {
  const url = (path: string) => new URL(path, "https://tracker.example");

  it("waits until the session has been checked", () => {
    expect(guardRedirect(url("/spools"), null, false)).toBeNull();
  });

  it("sends signed-out visitors to sign in", () => {
    expect(guardRedirect(url("/review"), null, true)).toBe("/login?next=%2Freview");
    expect(guardRedirect(url("/review"), null, true, true)).toBe("/login?next=%2Freview&expired=1");
  });

  it("lets signed-out visitors stay on the sign-in page", () => {
    expect(guardRedirect(url("/login"), null, true)).toBeNull();
  });

  it("sends signed-in users from the sign-in page to where they were going", () => {
    expect(guardRedirect(url("/login?next=/review"), ALICE, true)).toBe("/review");
    expect(guardRedirect(url("/login?next=//evil.example"), ALICE, true)).toBe("/");
  });

  it("leaves signed-in users on other pages", () => {
    expect(guardRedirect(url("/spools"), ALICE, true)).toBeNull();
  });
});
