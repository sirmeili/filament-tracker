<script lang="ts">
  import { page } from "$app/state";
  import { session } from "#lib/auth/session.svelte.ts";
  import LoginForm from "#lib/components/LoginForm.svelte";
  import { phone } from "#lib/phone/phone-state.svelte.ts";
</script>

<LoginForm {session} expired={page.url.searchParams.get("expired") === "1"} />
{#if phone.app}
  <!-- Pairing works without signing in, so a phone can be unlinked or paired again here. -->
  <p class="pairing">
    {#if !phone.paired && phone.server}
      Signing in to <span class="mono">{phone.server}</span>.
      <a href="/pair">Use a different server</a>
    {:else}
      <a href="/pair">Phone pairing</a>
    {/if}
  </p>
{/if}

<style>
  .pairing {
    margin: 16px 0 0;
    text-align: center;
  }
</style>
