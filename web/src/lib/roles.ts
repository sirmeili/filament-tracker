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
