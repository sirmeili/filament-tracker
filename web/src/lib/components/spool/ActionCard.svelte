<script lang="ts">
  import type { ManualAction, SpoolState } from "#lib/api/types.ts";
  import { actionsFor } from "#lib/spools.ts";

  interface Props {
    state: SpoolState;
    busy: boolean;
    /** The answer to the last action, such as "Flagged for review". */
    message: string | null;
    onaction: (action: ManualAction) => void;
  }

  let { state, busy, message, onaction }: Props = $props();
</script>

<section class="card" aria-labelledby="act-h">
  <div class="head">
    <h2 id="act-h" class="label">Record an action</h2>
    <span class="muted">Same rules as the scanner</span>
  </div>
  <div class="buttons">
    {#each actionsFor(state) as button (button.action)}
      <button
        type="button"
        class:primary={button.primary}
        disabled={busy}
        onclick={() => onaction(button.action)}>{button.label}</button
      >
    {/each}
  </div>
  {#if message}<p role="status">{message}</p>{/if}
</section>

<style>
  .head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 12px;
    font-size: 13px;
  }

  .buttons {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }

  .buttons button {
    flex: 1 1 160px;
  }

  p {
    margin: 0;
    font-size: 14px;
  }
</style>
