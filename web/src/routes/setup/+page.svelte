<script lang="ts">
  import { session } from "#lib/auth/session.svelte.ts";
  import SetupForm from "#lib/components/SetupForm.svelte";
</script>

<svelte:head><title>Set up · Filament Tracker</title></svelte:head>

{#if session.setup}
  <SetupForm status={session.setup} onsubmit={(fields) => session.finishSetup(fields)} />
{:else}
  <p class="muted">Loading…</p>
{/if}
