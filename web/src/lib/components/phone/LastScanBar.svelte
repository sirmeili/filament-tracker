<script lang="ts">
  import Ring from "#lib/components/ui/Ring.svelte";
  import { actionName, type LastScan } from "#lib/phone/scan-flow.ts";

  /** The last scan, at the bottom of the waiting screen, with its Undo. */
  interface Props {
    last: LastScan;
    onundo: () => void;
  }

  let { last, onundo }: Props = $props();
</script>

<div class="last">
  <Ring rgba={last.card.colorRgba ?? "00000000"} size="sm" />
  <div class="text">
    <div class="label">Last scan</div>
    <div class="what">
      {last.card.name} · {actionName(last.action)}{last.queued ? " (queued)" : ""}{last.undone
        ? " (undone)"
        : ""}
    </div>
  </div>
  {#if !last.undone}
    <button type="button" class="small" onclick={onundo}>Undo</button>
  {/if}
</div>

<style>
  .last {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 12px 12px 16px;
    border-radius: 16px;
    border: 1px solid var(--line);
    background: var(--surface);
  }

  .text {
    flex: 1;
    min-width: 0;
  }

  .label {
    font-size: 12px;
    font-weight: 600;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .what {
    font-size: 15px;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
</style>
