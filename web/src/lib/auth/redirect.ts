import type { Me } from "#lib/api/types.ts";

export const LOGIN_PATH = "/login";
export const SETUP_PATH = "/setup";

/** Where to go after signing in. Only paths on this site are allowed, so a crafted link
 * cannot send someone to another site after they sign in. */
export function safeNext(next: string | null | undefined): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) {
    return "/";
  }
  if (next === LOGIN_PATH || next.startsWith(LOGIN_PATH + "?")) return "/";
  return next;
}

/** The sign-in page, remembering where the user was going. */
export function loginUrl(pathname: string, search: string, expired = false): string {
  const params = new URLSearchParams();
  const next = pathname + search;
  if (next !== "/") params.set("next", next);
  if (expired) params.set("expired", "1");
  const query = params.toString();
  return query ? `${LOGIN_PATH}?${query}` : LOGIN_PATH;
}

/** The parts of the page URL the guard reads. */
export interface PageUrl {
  pathname: string;
  search: string;
  searchParams: { get(name: string): string | null };
}

/** Where the layout should send the browser, or null to stay. While first-start setup is
 * open, signed-out visitors go to Setup instead of sign-in. */
export function guardRedirect(
  url: PageUrl,
  user: Me | null,
  loaded: boolean,
  expired = false,
  setupOpen = false,
): string | null {
  if (!loaded) return null;
  const onSetup = url.pathname === SETUP_PATH;
  if (!user && setupOpen) return onSetup ? null : SETUP_PATH;
  if (onSetup) return user ? "/" : LOGIN_PATH;
  const onLogin = url.pathname === LOGIN_PATH;
  if (!user && !onLogin) return loginUrl(url.pathname, url.search, expired);
  if (user && onLogin) return safeNext(url.searchParams.get("next"));
  return null;
}
