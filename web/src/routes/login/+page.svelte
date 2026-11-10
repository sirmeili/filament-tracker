<script lang="ts">
  import { page } from "$app/state";
  import { session } from "#lib/auth/session.svelte.ts";
  import LoginForm from "#lib/components/LoginForm.svelte";
  import { phone } from "#lib/phone/phone-state.svelte.ts";
</script>

<LoginForm {session} expired={page.url.searchParams.get("expired") === "1"} />
{#if phone.app}
  <!-- Pairing works without signing in, so a phone can be unlinked or paired again here. -->
  <p class="pairing"><a href="/pair">Phone pairing</a></p>
{/if}

<style>
  .pairing {
    margin: 16px 0 0;
    text-align: center;
  }
</style>
