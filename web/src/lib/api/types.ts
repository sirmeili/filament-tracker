import type { Role } from "#lib/roles.ts";

/** The signed-in user (`GET /auth/me`). */
export interface Me {
  id: number;
  username: string;
  role: Role;
}
