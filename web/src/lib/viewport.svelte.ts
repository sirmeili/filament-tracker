/** Whether the screen is phone-sized (Server: web UI in docs/SPEC.md): 600px wide or less
 * gets the phone layout, with the bottom bar and the menu sheet. It follows the window as it
 * is resized or the phone is turned. */

export const PHONE_QUERY = "(max-width: 600px)";

export class Viewport {
  phone = $state(false);

  constructor(matchMedia: ((query: string) => MediaQueryList) | undefined = globalThis.matchMedia) {
    const media = matchMedia?.(PHONE_QUERY);
    this.phone = media?.matches ?? false;
    media?.addEventListener("change", (event) => (this.phone = event.matches));
  }
}

let shared: Viewport | undefined;

/** The app's viewport, created on first use (in the browser). */
export function viewport(): Viewport {
  shared ??= new Viewport();
  return shared;
}
