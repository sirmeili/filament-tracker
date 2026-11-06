<script lang="ts">
  import type { EventOut } from "#lib/api/types.ts";
  import Ring from "#lib/components/ui/Ring.svelte";
  import { timeOfDay } from "#lib/activity.ts";
  import { eventBy, eventTitle } from "#lib/format.ts";

  interface Props {
    event: EventOut;
    canUndo: boolean;
    busy: boolean;
    onundo: (event: EventOut) => void;
  }

  let { event, canUndo, busy, onundo }: Props = $props();
  const undone = $derived(event.reverted_by !== null);
</script>

<li>
  <span class="time mono">{timeOfDay(event.recorded_at)}</span>
  <Ring rgba={event.color_rgba} size="sm" />
  <a class="spool" href="/spools/{event.spool_id}">
    <span class="name" class:struck={undone}>{event.product_name}</span>
    <span class="id mono">#{event.spool_id}</span>
  </a>
  <span class="ev {event.type}">{eventTitle(event.type)}</span>
  {#if event.flagged && !undone}<span class="flag">Flagged</span>{/if}
  <span class="by">{eventBy(event)}</span>
  <span class="end">
    {#if undone}
      <span class="muted">Undone</span>
    {:else if canUndo && event.can_undo}
      <button
        type="button"
        class="small"
        disabled={busy}
        aria-label="Undo {eventTitle(event.type)} on {event.product_name} #{event.spool_id}"
        onclick={() => onundo(event)}>Undo</button
      >
    {/if}
  </span>
</li>

<style>
  li {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px 14px;
    padding: 12px 16px;
    border-top: 1px solid var(--line);
    font-size: 14px;
  }

  li:first-child {
    border-top: 0;
  }

  .time {
    width: 72px;
    color: var(--muted);
    font-size: 13px;
  }

  .spool {
    display: inline-flex;
    align-items: baseline;
    gap: 6px;
    min-width: 0;
    flex: 1 1 200px;
  }

  .name {
    font-family: var(--font-head);
    font-weight: 600;
    font-size: 15px;
  }

  .struck {
    text-decoration: line-through;
    color: var(--muted);
  }

  .id {
    font-size: 12px;
    color: var(--muted);
  }

  .ev {
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 3px 9px;
    border-radius: 6px;
    background: var(--chip);
    white-space: nowrap;
  }

  .ev.revert {
    background: transparent;
    border: 1px dashed var(--muted);
    color: var(--muted);
  }

  .flag {
    background: var(--lowbg);
    color: var(--lowtext);
    font-size: 11px;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 5px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .by {
    color: var(--muted);
    font-size: 13px;
    min-width: 140px;
  }

  .end {
    margin-left: auto;
    min-width: 70px;
    text-align: right;
  }
</style>
