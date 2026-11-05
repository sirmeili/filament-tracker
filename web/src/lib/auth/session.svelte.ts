import { api, ApiError, onUnauthorized } from "#lib/api/client.ts";
import type { Me } from "#lib/api/types.ts";
import { allows, type Role } from "#lib/roles.ts";

/** Who is signed in. `loaded` turns true once the first check has finished. */
export class Session {
  user = $state<Me | null>(null);
  loaded = $state(false);
  /** True when a signed-in session ended on its own (expired, or signed out elsewhere). */
  expired = $state(false);

  constructor() {
    onUnauthorized(() => {
      if (this.user) this.expired = true;
      this.user = null;
    });
  }

  async load(): Promise<void> {
    try {
      this.user = await api<Me>("/auth/me");
    } catch (error) {
      if (!(error instanceof ApiError) || (error.status !== 401 && error.status !== 403)) {
        throw error;
      }
      this.user = null;
    } finally {
      this.loaded = true;
    }
  }

  async login(username: string, password: string): Promise<Me> {
    const user = await api<Me>("/auth/login", { method: "POST", body: { username, password } });
    this.user = user;
    this.expired = false;
    return user;
  }

  async logout(): Promise<void> {
    try {
      await api<void>("/auth/logout", { method: "POST" });
    } finally {
      this.user = null;
      this.expired = false;
    }
  }

  can(needed: Role): boolean {
    return allows(this.user?.role, needed);
  }
}

export const session = new Session();
