import { describe, expect, it } from "vitest";
import { isThemeChoice, Theme, theme, THEME_KEY } from "#lib/theme.svelte.ts";

function storage(initial: Record<string, string> = {}): Storage {
  const data = new Map(Object.entries(initial));
  return {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => void data.set(key, value),
  } as Storage;
}

/** A prefers-color-scheme query whose answer the test can change. */
function device(dark: boolean) {
  let listener: ((event: { matches: boolean }) => void) | undefined;
  const query = {
    matches: dark,
    addEventListener: (_: string, fn: typeof listener) => (listener = fn),
  } as unknown as MediaQueryList;
  return {
    matchMedia: () => query,
    change(nowDark: boolean) {
      listener?.({ matches: nowDark });
    },
  };
}

describe("Theme", () => {
  it("follows the device by default", () => {
    const root = document.createElement("html");
    const screen = device(true);

    const theme = new Theme(root, storage(), screen.matchMedia);

    expect(theme.choice).toBe("system");
    expect(root.dataset.theme).toBe("dark");
    screen.change(false);
    expect(root.dataset.theme).toBe("light");
  });

  it("uses and saves a chosen theme", () => {
    const root = document.createElement("html");
    const saved = storage({ [THEME_KEY]: "light" });
    const screen = device(true);

    const theme = new Theme(root, saved, screen.matchMedia);
    expect(root.dataset.theme).toBe("light");

    theme.set("dark");
    expect(saved.getItem(THEME_KEY)).toBe("dark");
    expect(theme.resolved).toBe("dark");
    screen.change(false);
    expect(root.dataset.theme).toBe("dark");
  });

  it("ignores a bad saved value and blocked storage", () => {
    const root = document.createElement("html");
    const blocked = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    } as unknown as Storage;

    expect(new Theme(root, storage({ [THEME_KEY]: "neon" }), undefined).choice).toBe("system");
    const theme = new Theme(root, blocked, undefined);
    expect(theme.resolved).toBe("light");
    theme.set("dark");
    expect(root.dataset.theme).toBe("dark");
  });

  it("checks theme names and shares one theme", () => {
    expect(isThemeChoice("system")).toBe(true);
    expect(isThemeChoice("neon")).toBe(false);
    expect(theme()).toBe(theme());
  });
});
