/** Web app roles (Users and roles in docs/SPEC.md). Each role can do everything the
 * roles before it can. */
export type Role = "viewer" | "editor" | "admin";

const RANK: Record<Role, number> = { viewer: 0, editor: 1, admin: 2 };

export function allows(role: Role | null | undefined, needed: Role): boolean {
  return role != null && RANK[role] >= RANK[needed];
}

export const ROLE_LABELS: Record<Role, string> = {
  viewer: "Viewer",
  editor: "Editor",
  admin: "Admin",
};

export const ROLES: readonly Role[] = ["viewer", "editor", "admin"];

/** What each role can do, shown on the Users page. */
export const ROLE_DESCRIPTIONS: Record<Role, string> = {
  viewer: "sees every page.",
  editor:
    "also records actions, undoes, edits spools and products, adds spools by hand, and resolves review items.",
  admin: "also manages users, scanners, printers, machine tokens and settings.",
};
