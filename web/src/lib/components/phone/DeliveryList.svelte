<script lang="ts">
  import Ring from "#lib/components/ui/Ring.svelte";
  import { clockTime } from "#lib/format.ts";
  import { totalsText, type DeliveryRow, type DeliveryTotals } from "#lib/phone/delivery.svelte.ts";
  import { actionName } from "#lib/phone/scan-flow.ts";

  /** The spools scanned in this delivery, newest at the bottom, nearest the thumb. Only the
   * newest row can be undone, like the single Undo on the scanner. */
  interface Props {
    rows: DeliveryRow[];
    totals: DeliveryTotals;
    /** The event Undo would revert (the flow's last scan), if any. */
    undoable: string | null;
    /** The row just recorded, highlighted. */
    fresh: string | null;
    onundo: () => void;
    onclear: () => void;
  }

  let { rows, totals, undoable, fresh, onundo, onclear }: Props = $props();

  const newest = $derived(rows.at(-1) ?? null);
</script>

<div class="delivery">
  <div class="top">
    <h2 class="label">This delivery</h2>
    <span class="totals">{totalsText(totals)}</span>
    {#if rows.length}
      <button type="button" class="small" onclick={onclear}>Clear</button>
    {/if}
  </div>
  <div class="box">
    <ol class="rows" aria-label="Spools in this delivery">
      {#each rows as row (row.eventId)}
        <li class="row" class:fresh={row.eventId === fresh} class:undone={row.undone}>
          <Ring rgba={row.card.colorRgba ?? "00000000"} size="sm" />
          <div class="text">
            <div class="name">{row.card.name}</div>
            <div class="meta">
              {clockTime(row.at)}{row.card.spoolId ? ` · #${row.card.spoolId}` : ""}{row.queued
                ? " · queued"
                : ""}
            </div>
          </div>
          {#if row.undone}
            <span class="ev undone">Undone</span>
          {:else}
            <span class="ev {row.action}">{actionName(row.action)}</span>
          {/if}
          {#if row === newest && row.eventId === undoable && !row.undone}
            <button type="button" class="small" onclick={onundo}>Undo</button>
          {/if}
        </li>
      {:else}
        <li class="empty muted">Spools you scan show up here.</li>
      {/each}
    </ol>
  </div>
</div>

<style>
  .delivery {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 10px 20px 0;
  }

  .top {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .label {
    margin: 0;
    flex: 1;
    font-size: 12px;
    font-weight: 600;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .totals {
    font-size: 13px;
    color: var(--muted);
  }

  .box {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column-reverse;
    border-radius: 16px;
    border: 1px solid var(--line);
    background: var(--surface);
  }

  .rows {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    min-height: 100%;
  }

  .row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 11px 16px;
    min-height: 48px;
    border-top: 1px solid var(--line);
  }

  .row:first-child {
    border-top: 0;
  }

  .row.fresh {
    background: var(--okbg);
  }

  .text {
    flex: 1;
    min-width: 0;
  }

  .name {
    font-size: 15px;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .undone .name {
    text-decoration: line-through;
    color: var(--muted);
  }

  .meta {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--muted);
  }

  .ev {
    font-size: 11px;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 6px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    white-space: nowrap;
    border: 1px solid transparent;
  }

  .ev.received {
    background: var(--text);
    color: var(--bg);
  }

  .ev.opened {
    background: var(--chip);
    color: var(--text);
    border-color: var(--line);
  }

  .ev.empty,
  .ev.undone {
    color: var(--muted);
    border: 1px dashed var(--muted);
  }

  .empty {
    margin: auto;
    padding: 24px;
    text-align: center;
    font-size: 15px;
  }
</style>
