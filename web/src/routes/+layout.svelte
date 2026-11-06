<script lang="ts">
  import "#lib/fonts.ts";
  import "../app.css";

  import type { Snippet } from "svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import { guardRedirect, LOGIN_PATH } from "#lib/auth/redirect.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import Forbidden from "#lib/components/Forbidden.svelte";
  import Header from "#lib/components/Header.svelte";
  import { requiredRole } from "#lib/nav.ts";
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

  $effect(() => {
    if (!session.loaded) void load();
  });

  // Send signed-out visitors to the sign-in page, and signed-in ones away from it.
  $effect(() => {
    const target = guardRedirect(page.url, session.user, session.loaded, session.expired);
    if (target) void goto(target, { replaceState: true });
  });

  // The Review badge, refreshed on every page change.
  $effect(() => {
    void page.url.pathname;
    if (session.user) void reviewBadge.refresh();
  });
</script>

{#if page.url.pathname === LOGIN_PATH}
  <main class="centered">{@render children()}</main>
{:else if session.user}
  <Header
    user={session.user}
    pathname={page.url.pathname}
    theme={appTheme}
    reviewCount={reviewBadge.count}
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
