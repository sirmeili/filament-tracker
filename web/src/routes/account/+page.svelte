<script lang="ts">
  import { goto } from "$app/navigation";
  import { LOGIN_PATH } from "#lib/auth/redirect.ts";
  import { session } from "#lib/auth/session.svelte.ts";
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

<section>
  <h1>Account</h1>
  {#if session.user}
    <dl>
      <dt>Username</dt>
      <dd>{session.user.username}</dd>
      <dt>Role</dt>
      <dd>{ROLE_LABELS[session.user.role]}</dd>
    </dl>
  {/if}
  <p class="muted">Changing your password arrives with the account page in a later part of M2.</p>
  <button class="primary" onclick={signOut} disabled={busy}>Sign out</button>
</section>
