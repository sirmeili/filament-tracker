import { api, ApiError, onUnauthorized } from "#lib/api/client.ts";
import { finishSetup, openSetup, type SetupFields, type SetupStatus } from "#lib/api/setup.ts";
import type { Me } from "#lib/api/types.ts";
import { setTimeZone } from "#lib/format.ts";
import { allows, type Role } from "#lib/roles.ts";

/** Who is signed in. `loaded` turns true once the first check has finished. */
export class Session {
  #user = $state<Me | null>(null);
  loaded = $state(false);
  /** True when a signed-in session ended on its own (expired, or signed out elsewhere). */
  expired = $state(false);
  /** First-start setup, while it is open (no Admin yet); then null. */
  setup = $state<SetupStatus | null>(null);

  get user(): Me | null {
    return this.#user;
  }

  /** The signed-in user; their time zone becomes the one every time is shown in. */
  set user(user: Me | null) {
    this.#user = user;
    if (user) setTimeZone(user.time_zone);
  }

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
      this.setup = await openSetup();
    } finally {
      this.loaded = true;
    }
  }

  /** Create the first Admin, who is then signed in. */
  async finishSetup(fields: SetupFields): Promise<Me> {
    const user = await finishSetup(fields);
    this.user = user;
    this.setup = null;
    this.expired = false;
    return user;
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
