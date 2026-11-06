/** The Light / Dark / System theme choice (Server: web UI in docs/SPEC.md), remembered in
 * the browser. The script in app.html applies the saved choice before the page draws; this
 * keeps it applied afterwards, following the device while the choice is System. */

export type ThemeChoice = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export const THEME_KEY = "ft-theme";
export const THEME_CHOICES: readonly ThemeChoice[] = ["light", "dark", "system"];
const DARK_QUERY = "(prefers-color-scheme: dark)";

export function isThemeChoice(value: unknown): value is ThemeChoice {
  return THEME_CHOICES.includes(value as ThemeChoice);
}

function readStored(storage: Storage | undefined): ThemeChoice {
  try {
    const value = storage?.getItem(THEME_KEY);
    return isThemeChoice(value) ? value : "system";
  } catch {
    return "system"; // storage blocked
  }
}

export class Theme {
  choice = $state<ThemeChoice>("system");
  #deviceDark = $state(false);
  #media: MediaQueryList | undefined;
  readonly root: HTMLElement;
  readonly storage: Storage | undefined;

  constructor(
    root: HTMLElement = document.documentElement,
    storage: Storage | undefined = globalThis.localStorage,
    matchMedia: ((query: string) => MediaQueryList) | undefined = globalThis.matchMedia,
  ) {
    this.root = root;
    this.storage = storage;
    this.choice = readStored(storage);
    this.#media = matchMedia?.(DARK_QUERY);
    this.#deviceDark = this.#media?.matches ?? false;
    this.#media?.addEventListener("change", (event) => {
      this.#deviceDark = event.matches;
      this.#apply();
    });
    this.#apply();
  }

  get resolved(): ResolvedTheme {
    if (this.choice === "system") return this.#deviceDark ? "dark" : "light";
    return this.choice;
  }

  set(choice: ThemeChoice): void {
    this.choice = choice;
    try {
      this.storage?.setItem(THEME_KEY, choice);
    } catch {
      // Storage blocked: the choice lasts until the page is reloaded.
    }
    this.#apply();
  }

  #apply(): void {
    this.root.dataset.theme = this.resolved;
  }
}

let shared: Theme | undefined;

/** The app's theme, created on first use (in the browser). */
export function theme(): Theme {
  shared ??= new Theme();
  return shared;
}
