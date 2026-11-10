<script lang="ts">
  import "#lib/fonts.ts";
  import "../app.css";

  import type { Snippet } from "svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import { guardRedirect, LOGIN_PATH, SETUP_PATH } from "#lib/auth/redirect.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import Forbidden from "#lib/components/Forbidden.svelte";
  import Header from "#lib/components/Header.svelte";
  import StartScreen from "#lib/components/phone/StartScreen.svelte";
  import PhoneNav from "#lib/components/shell/PhoneNav.svelte";
  import PhoneTopBar from "#lib/components/shell/PhoneTopBar.svelte";
  import { pageTitle, requiredRole } from "#lib/nav.ts";
  import { isPhonePath, phone } from "#lib/phone/phone-state.svelte.ts";
  import { reviewBadge } from "#lib/review-badge.svelte.ts";
  import { theme } from "#lib/theme.svelte.ts";
  import { viewport } from "#lib/viewport.svelte.ts";

  let { children }: { children: Snippet } = $props();

  /** How long the app waits before asking a second time whether someone is signed in. */
  const SIGN_IN_RETRY_MS = 500;

  // Applies the saved theme; the choice itself is on the Account page.
  theme();
  const screen = viewport();
  let loadError = $state<string | null>(null);
  // The phone app's start screen, shown once per launch until the app is ready.
  let started = $state(false);

  async function load(): Promise<void> {
    loadError = null;
    try {
      // In the app, check a "not signed in" answer once more (see Session.load).
      await session.load(phone.app ? SIGN_IN_RETRY_MS : 0);
    } catch {
      loadError = "Cannot reach the server.";
    }
  }

  // In the phone app, Scan and Pairing work without signing in (the phone is a scanner),
  // and until a server is chosen or the phone is paired there is no server to sign in to.
  const phonePage = $derived(
    phone.app && (isPhonePath(page.url.pathname) || (!phone.paired && !phone.server)),
  );
  // A phone being set up by signing in needs the sign-in even on Pairing.
  const wantsSession = $derived(
    !phonePage || (phone.app && !phone.paired && phone.server !== null),
  );
  // Ready: the pairing is loaded, for a paired phone the server has answered or not, and
  // the sign-in check has finished when the first page needs it (so the sign-in page never
  // flashes up while the check is still going).
  const startReady = $derived(
    phone.loaded &&
      (!phone.paired || phone.reach !== null) &&
      (!wantsSession || session.loaded || loadError !== null),
  );

  let openedAt = page.url.pathname;

  $effect(() => {
    if (phone.app && !phone.loaded) void phone.load();
  });

  $effect(() => {
    if (!phone.app || !phone.loaded) return;
    const onPair = page.url.pathname === "/pair";
    if (!phone.paired && !phone.server && !onPair) {
      void goto("/pair", { replaceState: true });
    } else if (!phone.paired && phone.server && session.user && !onPair) {
      // Signed in: finish setting the phone up.
      void goto("/pair", { replaceState: true });
    } else if (phone.paired && openedAt === "/") {
      // The app opens where this phone was set to: Scan (the default) or Inventory.
      openedAt = "";
      if (phone.openOn !== "stock") void goto("/scan", { replaceState: true });
    }
  });

  $effect(() => {
    if (phone.app && !phone.loaded) return;
    if (wantsSession && !session.loaded) void load();
  });

  // Send signed-out visitors to the sign-in page, and signed-in ones away from it.
  $effect(() => {
    if (phonePage) return;
    const target = guardRedirect(
      page.url,
      session.user,
      session.loaded,
      session.expired,
      session.setup !== null,
    );
    if (target) void goto(target, { replaceState: true });
  });

  // The Review badge, refreshed on every page change.
  $effect(() => {
    void page.url.pathname;
    if (session.user) void reviewBadge.refresh();
  });
</script>

{#if phone.app && !started}
  <StartScreen ready={startReady} ondone={() => (started = true)} />
{:else if phonePage}
  <main class:bare={page.url.pathname === "/scan"}>{@render children()}</main>
{:else if page.url.pathname === LOGIN_PATH || page.url.pathname === SETUP_PATH}
  <main class="centered">{@render children()}</main>
{:else if session.user}
  {#if screen.phone}
    <PhoneTopBar title={pageTitle(page.url.pathname)} />
  {:else}
    <Header
      user={session.user}
      pathname={page.url.pathname}
      reviewCount={reviewBadge.count}
      scan={phone.app}
    />
  {/if}
  <main class:phone={screen.phone}>
    {#if session.can(requiredRole(page.url.pathname))}
      {@render children()}
    {:else}
      <Forbidden />
    {/if}
  </main>
  {#if screen.phone}
    <PhoneNav
      user={session.user}
      pathname={page.url.pathname}
      reviewCount={reviewBadge.count}
      scan={phone.app}
    />
  {/if}
{:else if loadError}
  <main class="centered">
    <p role="alert" class="error">{loadError}</p>
    <button class="primary" onclick={load}>Try again</button>
    {#if phone.app}
      <!-- The way out when the paired server is gone: Pairing works without it. -->
      <a class="button" href="/pair">Phone pairing</a>
    {/if}
  </main>
{:else}
  <main class="centered"><p class="muted">Loading…</p></main>
{/if}

<style>
  main {
    max-width: 1240px;
    margin: 0 auto;
    padding: 32px 24px 56px;
  }

  main.bare {
    padding: 0;
  }

  /* Room for the bottom bar; the top bar shows the title, so the page's own stays for
     screen readers only. */
  main.phone {
    padding: 4px 16px calc(var(--bottom-bar) + 24px);
  }

  main.phone :global(.pagehead h1) {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
  }

  @media (max-width: 600px) {
    main {
      padding: 20px 16px 40px;
    }
  }

  .centered {
    display: grid;
    place-items: center;
    align-content: center;
    gap: 1rem;
    min-height: 80vh;
  }
</style>
