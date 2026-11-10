import { allows, type Role } from "#lib/roles.ts";

export interface NavItem {
  href: string;
  label: string;
  role: Role;
}

/** Reached from the account button in the header rather than the nav links. Any signed-in
 * user may open it. */
export const ACCOUNT_PATH = "/account";

/** The pages in the Server: web UI table of docs/SPEC.md, with the lowest role that may
 * open each. The API enforces the same rules. */
export const NAV: readonly NavItem[] = [
  { href: "/", label: "Inventory", role: "viewer" },
  { href: "/spools", label: "Spools", role: "viewer" },
  { href: "/products", label: "Products", role: "viewer" },
  { href: "/review", label: "Review", role: "viewer" },
  { href: "/activity", label: "Activity", role: "viewer" },
  { href: "/devices", label: "Devices", role: "admin" },
  { href: "/users", label: "Users", role: "admin" },
  { href: "/settings", label: "Settings", role: "admin" },
];

export function visibleNav(role: Role | null | undefined): NavItem[] {
  return NAV.filter((item) => allows(role, item.role));
}

function matches(item: NavItem, pathname: string): boolean {
  if (item.href === "/") return pathname === "/";
  return pathname === item.href || pathname.startsWith(item.href + "/");
}

/** The nav item a path belongs to: the page itself or one of its sub-pages. */
export function navItemFor(pathname: string): NavItem | undefined {
  return NAV.find((item) => matches(item, pathname));
}

/** The lowest role that may open a path; pages not in the nav need a Viewer. */
export function requiredRole(pathname: string): Role {
  return navItemFor(pathname)?.role ?? "viewer";
}

/** Titles for pages that are not in the nav (or are sub-pages with their own name). */
const TITLES: Record<string, string> = {
  "/account": "Account",
  "/spools/new": "Add a spool",
};

/** The title the phone layout's top bar shows for a path. */
export function pageTitle(pathname: string): string {
  return TITLES[pathname] ?? navItemFor(pathname)?.label ?? "RollCall";
}

/** The pages anyone may open, and the Admin ones, as the phone menu groups them. */
export function menuGroups(role: Role | null | undefined): { main: NavItem[]; admin: NavItem[] } {
  const items = visibleNav(role);
  return {
    main: items.filter((item) => item.role !== "admin"),
    admin: items.filter((item) => item.role === "admin"),
  };
}
