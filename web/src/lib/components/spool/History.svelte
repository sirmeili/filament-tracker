<script lang="ts">
  import type { EventOut } from "#lib/api/types.ts";
  import { dateTime, eventBy, eventTitle } from "#lib/format.ts";

  interface Props {
    /** Newest first */
    events: EventOut[];
    canUndo: boolean;
    busy: boolean;
    onundo: (event: EventOut) => void;
  }

  let { events, canUndo, busy, onundo }: Props = $props();

  function title(event: EventOut): string {
    if (event.type !== "revert") return eventTitle(event.type);
    const target = events.find((e) => e.id === event.reverts);
    return target ? `Undid “${eventTitle(target.type)}”` : "Undo";
  }
</script>

<section class="card" aria-labelledby="hist-h">
  <h2 id="hist-h" class="label">History</h2>
  {#if events.length === 0}
    <p class="muted">No events.</p>
  {:else}
    <ol>
      {#each events as event (event.id)}
        {@const undone = event.reverted_by !== null}
        <li>
          <span class="dot" class:rev={event.type === "revert" || undone} aria-hidden="true"></span>
          <div class="body">
            <div class="head">
              <strong class:struck={undone}>{title(event)}</strong>
              {#if undone}<span class="sr-only">(undone)</span>{/if}
              {#if event.flagged}<span class="flag">Flagged</span>{/if}
            </div>
            <div class="meta">
              <span class="mono">{dateTime(event.occurred_at)}</span> · {eventBy(event)}
            </div>
          </div>
          {#if canUndo && event.can_undo}
            <button
              type="button"
              class="small"
              disabled={busy}
              aria-label="Undo {eventTitle(event.type)}, {dateTime(event.occurred_at)}"
              onclick={() => onundo(event)}>Undo</button
            >
          {/if}
        </li>
      {/each}
    </ol>
  {/if}
</section>

<style>
  ol {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  li {
    display: flex;
    align-items: flex-start;
    gap: 14px;
    padding: 14px 0;
    border-top: 1px solid var(--line);
  }

  li:first-child {
    border-top: 0;
    padding-top: 0;
  }

  .dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    margin-top: 5px;
    flex: none;
    background: var(--text);
  }

  .dot.rev {
    background: transparent;
    border: 2px solid var(--muted);
  }

  .body {
    flex: 1;
    min-width: 0;
  }

  .head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    font-size: 15px;
  }

  .struck {
    text-decoration: line-through;
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

  .meta {
    margin-top: 3px;
    font-size: 13px;
    color: var(--muted);
  }

  p {
    margin: 0;
  }
</style>
