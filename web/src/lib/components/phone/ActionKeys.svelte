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
        class="key"
        class:primary={action === suggested}
        aria-describedby={action === suggested ? "suggested-note" : undefined}
        disabled={busy}
        onclick={() => onchoose(action)}
        >{actionLabel(action)}{#if action === suggested}<small aria-hidden="true">Suggested</small
          >{/if}</button
      >
    {:else}
      <span></span>
    {/if}
  {/each}
</div>
{#if suggested}<span id="suggested-note" hidden>Suggested</span>{/if}

<style>
  .keys {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
  }

  .key {
    min-height: 72px;
    padding: 0 6px;
    border-radius: 16px;
    font-size: 17px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
  }

  small {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    opacity: 0.85;
  }
</style>
