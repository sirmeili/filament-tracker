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
  import { requiredRole } from "#lib/nav.ts";
  import { isPhonePath, phone } from "#lib/phone/phone-state.svelte.ts";
  import { reviewBadge } from "#lib/review-badge.svelte.ts";
  import { theme } from "#lib/theme.svelte.ts";

  let { children }: { children: Snippet } = $props();

  const appTheme = theme();
  let loadError = $state<string | null>(null);

  async function load(): Promise<void> {
    loadError = null;
    try {
      await session.load();
    } catch {
      loadError = "Cannot reach the server.";
    }
  }

  // In the phone app, Scan and Pairing work without signing in (the phone is a scanner),
  // and until the phone is paired there is no server to sign in to.
  const phonePage = $derived(phone.app && (isPhonePath(page.url.pathname) || !phone.paired));
  let openedAt = page.url.pathname;

  $effect(() => {
    if (phone.app && !phone.loaded) void phone.load();
  });

  $effect(() => {
    if (!phone.app || !phone.loaded) return;
    if (!phone.paired && page.url.pathname !== "/pair") {
      void goto("/pair", { replaceState: true });
    } else if (phone.paired && openedAt === "/") {
      // The app opens on Scan; the rest of the web app is a link away.
      openedAt = "";
      void goto("/scan", { replaceState: true });
    }
  });

  $effect(() => {
    if (phone.app && !phone.loaded) return;
    if (!phonePage && !session.loaded) void load();
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

{#if phone.app && !phone.loaded}
  <main class="centered"><p class="muted">Loading…</p></main>
{:else if phonePage}
  <main class:bare={page.url.pathname === "/scan"}>{@render children()}</main>
{:else if page.url.pathname === LOGIN_PATH || page.url.pathname === SETUP_PATH}
  <main class="centered">{@render children()}</main>
{:else if session.user}
  <Header
    user={session.user}
    pathname={page.url.pathname}
    theme={appTheme}
    reviewCount={reviewBadge.count}
    scan={phone.app}
  />
  <main>
    {#if session.can(requiredRole(page.url.pathname))}
      {@render children()}
    {:else}
      <Forbidden />
    {/if}
  </main>
{:else if loadError}
  <main class="centered">
    <p role="alert" class="error">{loadError}</p>
    <button class="primary" onclick={load}>Try again</button>
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
