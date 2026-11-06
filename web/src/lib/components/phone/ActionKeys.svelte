<script lang="ts">
  import type { ScreenAction } from "#lib/phone/device-api.ts";
  import { actionLabel } from "#lib/phone/scan-flow.ts";

  interface Props {
    actions: (ScreenAction | null)[];
    suggested: ScreenAction | null;
    busy: boolean;
    onchoose: (action: ScreenAction) => void;
  }

  let { actions, suggested, busy, onchoose }: Props = $props();
</script>

<div class="keys" role="group" aria-label="Actions">
  {#each actions as action, slot (slot)}
    {#if action}
      <button
        type="button"
        class:primary={action === suggested}
        aria-describedby={action === suggested ? "suggested-note" : undefined}
        disabled={busy}
        onclick={() => onchoose(action)}>{actionLabel(action)}</button
      >
    {:else}
      <span></span>
    {/if}
  {/each}
</div>
{#if suggested}<p id="suggested-note" class="muted small">Highlighted: the suggested action</p>{/if}

<style>
  .keys {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
  }

  button {
    min-height: 56px;
    font-size: 17px;
  }

  .small {
    margin: 0;
    font-size: 13px;
  }
</style>
