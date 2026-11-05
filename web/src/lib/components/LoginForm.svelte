<script lang="ts">
  import { ApiError } from "#lib/api/client.ts";
  import type { Session } from "#lib/auth/session.svelte.ts";

  interface Props {
    session: Session;
    /** The previous session ended on its own. */
    expired?: boolean;
  }

  let { session, expired = false }: Props = $props();

  let username = $state("");
  let password = $state("");
  let busy = $state(false);
  let error = $state<string | null>(null);

  function messageFor(failure: unknown): string {
    if (failure instanceof ApiError) {
      if (failure.status === 401) return "Wrong username or password.";
      if (failure.status === 429) return "Too many failed attempts. Try again in a few minutes.";
      return failure.message;
    }
    return "Something went wrong. Try again.";
  }

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    busy = true;
    error = null;
    try {
      await session.login(username, password);
    } catch (failure) {
      error = messageFor(failure);
      password = "";
    } finally {
      busy = false;
    }
  }
</script>

<form onsubmit={submit} aria-labelledby="login-title">
  <h1 id="login-title">Sign in</h1>
  {#if expired && !error}
    <p class="notice" role="status">Your session ended. Sign in again to continue.</p>
  {/if}
  {#if error}
    <p class="error" role="alert">{error}</p>
  {/if}
  <label>
    Username
    <input
      name="username"
      autocomplete="username"
      autocapitalize="none"
      spellcheck="false"
      required
      bind:value={username}
    />
  </label>
  <label>
    Password
    <input
      name="password"
      type="password"
      autocomplete="current-password"
      required
      bind:value={password}
    />
  </label>
  <button type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
</form>

<style>
  form {
    display: grid;
    gap: 1rem;
    width: min(100%, 22rem);
    padding: 1.5rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-large);
    background: var(--surface);
  }

  h1 {
    margin: 0;
    font-size: 1.4rem;
  }

  label {
    display: grid;
    gap: 0.3rem;
    font-weight: 600;
  }
</style>
