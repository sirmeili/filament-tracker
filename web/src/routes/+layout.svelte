<script lang="ts">
  import "../app.css";

  import type { Snippet } from "svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import { guardRedirect, LOGIN_PATH } from "#lib/auth/redirect.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import Forbidden from "#lib/components/Forbidden.svelte";
  import Nav from "#lib/components/Nav.svelte";
  import { navItemFor, requiredRole, visibleNav } from "#lib/nav.ts";
  import { ROLE_LABELS } from "#lib/roles.ts";

  let { children }: { children: Snippet } = $props();

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
</script>

{#if page.url.pathname === LOGIN_PATH}
  <main class="centered">{@render children()}</main>
{:else if session.user}
  <header>
    <a class="brand" href="/">Filament Tracker</a>
    <Nav items={visibleNav(session.user.role)} current={navItemFor(page.url.pathname)} />
    <span class="who">{session.user.username} · {ROLE_LABELS[session.user.role]}</span>
  </header>
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
    <button onclick={load}>Try again</button>
  </main>
{:else}
  <main class="centered"><p class="muted">Loading…</p></main>
{/if}

<style>
  header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem 1rem;
    padding: 0.5rem 1rem;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
  }

  .brand {
    font-weight: 700;
    color: var(--text);
    text-decoration: none;
  }

  .who {
    margin-left: auto;
    color: var(--muted);
    font-size: 0.9rem;
  }

  main {
    padding: 1rem;
    max-width: 72rem;
    margin: 0 auto;
  }

  .centered {
    display: grid;
    place-items: center;
    gap: 1rem;
    min-height: 80vh;
  }
</style>
