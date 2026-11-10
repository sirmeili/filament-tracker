<script lang="ts">
  import { goto } from "$app/navigation";
  import { LOGIN_PATH } from "#lib/auth/redirect.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import ChangePassword from "#lib/components/account/ChangePassword.svelte";
  import { phone } from "#lib/phone/phone-state.svelte.ts";
  import { ROLE_LABELS } from "#lib/roles.ts";

  let busy = $state(false);

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
    <ChangePassword />
  {/if}

  {#if phone.app}
    <section class="card signout" aria-labelledby="phone-h">
      <div>
        <h2 id="phone-h" class="label">This phone</h2>
        <p class="muted">Its pairing with the server, used for scanning.</p>
      </div>
      <a class="button" href="/pair">Phone pairing</a>
    </section>
  {/if}

  <section class="card signout" aria-labelledby="so-h">
    <div>
      <h2 id="so-h" class="label">Sign out</h2>
      <p class="muted">Ends this session on this device.</p>
    </div>
    <button type="button" onclick={signOut} disabled={busy}>Sign out</button>
  </section>
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

  .signout {
    max-width: 560px;
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
  }

  .signout p {
    margin: 6px 0 0;
    font-size: 14px;
  }
</style>
