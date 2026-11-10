<script lang="ts">
  // Account (docs/mockups/mobile-web/PhoneAccount.dc.html): Appearance, the password, this
  // phone (in the app) and Sign out, at every screen size.
  import { goto } from "$app/navigation";
  import { LOGIN_PATH } from "#lib/auth/redirect.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import AppearanceChoice from "#lib/components/account/AppearanceChoice.svelte";
  import ChangePassword from "#lib/components/account/ChangePassword.svelte";
  import { phone } from "#lib/phone/phone-state.svelte.ts";
  import { ROLE_LABELS } from "#lib/roles.ts";
  import { theme } from "#lib/theme.svelte.ts";

  const appTheme = theme();
  let busy = $state(false);
  let changing = $state(false);

  async function signOut(): Promise<void> {
    busy = true;
    try {
      await session.logout();
    } finally {
      busy = false;
      await goto(LOGIN_PATH, { replaceState: true });
    }
  }
</script>

<svelte:head><title>Account · RollCall</title></svelte:head>

<div class="page">
  {#if session.user}
    <div class="who">
      <span class="av" aria-hidden="true">{session.user.username.charAt(0).toUpperCase()}</span>
      <div>
        <h1>{session.user.username}</h1>
        <p class="muted">{ROLE_LABELS[session.user.role]}</p>
      </div>
    </div>
  {/if}

  <AppearanceChoice theme={appTheme} />

  <section class="card rows" aria-label="Account actions">
    {#if session.user}
      <button
        type="button"
        class="row"
        aria-expanded={changing}
        aria-controls="change-password"
        onclick={() => (changing = !changing)}
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          aria-hidden="true"
          ><rect x="4" y="11" width="16" height="10" rx="2"></rect><path d="M8 11V7a4 4 0 0 1 8 0v4"
          ></path></svg
        >
        <span class="grow">Change password</span>
        <span class="chev" class:open={changing} aria-hidden="true">›</span>
      </button>
    {/if}
    {#if phone.app}
      <a class="row" href="/pair">
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          aria-hidden="true"
          ><rect x="5" y="2" width="14" height="20" rx="2"></rect><path d="M12 18h.01"></path></svg
        >
        <span class="grow">This phone</span>
        <span class="state">{phone.paired ? "Paired" : "Not set up"}</span>
      </a>
    {/if}
  </section>

  {#if changing}
    <div id="change-password"><ChangePassword /></div>
  {/if}

  <button type="button" class="signout" onclick={signOut} disabled={busy}>Sign out</button>
</div>

<style>
  .who {
    display: flex;
    align-items: center;
    gap: 18px;
  }

  .av {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    background: var(--chip);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-family: var(--font-head);
    font-weight: 700;
    font-size: 28px;
  }

  .who p {
    margin: 4px 0 0;
    font-size: 15px;
  }

  .rows {
    max-width: 560px;
    gap: 0;
    padding: 4px 16px;
  }

  .row {
    display: flex;
    align-items: center;
    gap: 12px;
    min-height: 52px;
    padding: 0;
    border: 0;
    border-top: 1px solid var(--line);
    border-radius: 0;
    background: transparent;
    color: var(--text);
    font-size: 16px;
    font-weight: 600;
    text-align: left;
  }

  .row:first-child {
    border-top: 0;
  }

  .grow {
    flex: 1;
  }

  .state {
    color: var(--muted);
    font-size: 14px;
    font-weight: 500;
  }

  .chev {
    color: var(--muted);
    font-size: 20px;
    transition: transform 0.15s;
  }

  .chev.open {
    transform: rotate(90deg);
  }

  .rows:empty {
    display: none;
  }

  .signout {
    max-width: 560px;
    min-height: 52px;
    font-size: 16px;
    font-weight: 600;
  }
</style>
