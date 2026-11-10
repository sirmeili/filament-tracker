<script lang="ts">
  import { ACTIVITY_PAGE, groupByDay, SOURCE_FILTERS } from "#lib/activity.ts";
  import { listEvents } from "#lib/api/admin.ts";
  import { describeError } from "#lib/api/errors.ts";
  import { undoEvent } from "#lib/api/stock.ts";
  import type { EventOut, EventSource } from "#lib/api/types.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import EventRow from "#lib/components/activity/EventRow.svelte";
  import { eventTitle } from "#lib/format.ts";

  let source = $state<EventSource | "all">("all");
  let events = $state<EventOut[] | null>(null);
  let total = $state(0);
  let failure = $state<string | null>(null);
  let message = $state<string | null>(null);
  let busy = $state(false);

  const canEdit = $derived(session.can("editor"));
  const days = $derived(groupByDay(events ?? []));

  /** Load the first `count` events for the current filter. */
  async function load(count: number): Promise<void> {
    try {
      const page = await listEvents({
        source: source === "all" ? undefined : source,
        limit: count,
        offset: 0,
      });
      events = page.items;
      total = page.total;
      failure = null;
    } catch (error) {
      failure = describeError(error);
    }
  }

  $effect(() => {
    void source;
    events = null;
    void load(ACTIVITY_PAGE);
  });

  /** Add the next page after `shown`, the events on screen. */
  async function older(shown: EventOut[]): Promise<void> {
    busy = true;
    try {
      const page = await listEvents({
        source: source === "all" ? undefined : source,
        limit: ACTIVITY_PAGE,
        offset: shown.length,
      });
      const seen = new Set(shown.map((e) => e.id));
      events = [...shown, ...page.items.filter((e) => !seen.has(e.id))];
      total = page.total;
    } catch (error) {
      message = describeError(error);
    } finally {
      busy = false;
    }
  }

  async function undo(event: EventOut): Promise<void> {
    busy = true;
    message = null;
    try {
      await undoEvent(event.id);
      message = `Undid “${eventTitle(event.type)}” on ${event.product_name} #${event.spool_id}.`;
      // The undo is a new event at the top; reload everything shown so far.
      await load(Math.min((events?.length ?? 0) + 1, 200));
    } catch (error) {
      message = describeError(error);
    } finally {
      busy = false;
    }
  }
</script>

<svelte:head><title>Activity · RollCall</title></svelte:head>

<div class="page">
  <div class="pagehead">
    <div>
      <h1>Activity</h1>
      <p>Every event from scanners, the printer and the web app, newest first.</p>
    </div>
  </div>

  <div class="toolbar chips" role="group" aria-label="Filter by source">
    {#each SOURCE_FILTERS as option (option.value)}
      <button
        type="button"
        class="chip"
        aria-pressed={source === option.value}
        onclick={() => (source = option.value)}>{option.label}</button
      >
    {/each}
  </div>

  {#if message}<p role="status" class="muted">{message}</p>{/if}

  {#if failure}
    <p role="alert" class="error">{failure}</p>
  {:else if !events}
    <p class="muted">Loading…</p>
  {:else if events.length === 0}
    <p class="muted">No events yet.</p>
  {:else}
    {#each days as day (day.label)}
      <section aria-label={day.label}>
        <h2 class="label">{day.label}</h2>
        <ul>
          {#each day.events as event (event.id)}
            <EventRow {event} canUndo={canEdit} {busy} onundo={undo} />
          {/each}
        </ul>
      </section>
    {/each}
    {#if events.length < total}
      <button
        type="button"
        class="chip older"
        disabled={busy}
        onclick={() => older(events as EventOut[])}>Load older</button
      >
    {/if}
  {/if}
</div>

<style>
  .chips {
    gap: 8px;
  }

  section {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  ul {
    margin: 0;
    padding: 0;
    list-style: none;
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 16px;
  }

  .older {
    align-self: center;
  }
</style>
