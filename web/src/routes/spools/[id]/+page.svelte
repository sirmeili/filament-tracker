<script lang="ts">
  import { page } from "$app/state";
  import { describeError } from "#lib/api/errors.ts";
  import { getSpool, recordAction, undoEvent, updateSpool } from "#lib/api/stock.ts";
  import type { EventOut, ManualAction, SpoolDetail } from "#lib/api/types.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import ActionCard from "#lib/components/spool/ActionCard.svelte";
  import History from "#lib/components/spool/History.svelte";
  import LeftOnSpool from "#lib/components/spool/LeftOnSpool.svelte";
  import TagData from "#lib/components/spool/TagData.svelte";
  import WhereNotes from "#lib/components/spool/WhereNotes.svelte";
  import Ring from "#lib/components/ui/Ring.svelte";
  import StateChip from "#lib/components/ui/StateChip.svelte";
  import { eventTitle, hexText } from "#lib/format.ts";
  import { outcomeText, statusLine } from "#lib/spools.ts";

  const id = $derived(Number(page.params.id));

  let spool = $state<SpoolDetail | null>(null);
  let failure = $state<string | null>(null);
  let busy = $state(false);
  let message = $state<string | null>(null);

  const canEdit = $derived(session.can("editor"));

  async function load(spoolId: number): Promise<void> {
    failure = null;
    try {
      spool = await getSpool(spoolId);
    } catch (error) {
      failure = describeError(error);
    }
  }

  $effect(() => {
    spool = null;
    message = null;
    if (Number.isInteger(id) && id > 0) void load(id);
    else failure = "Not found. It may have been removed.";
  });

  async function act(action: ManualAction): Promise<void> {
    busy = true;
    message = null;
    try {
      const result = await recordAction(id, action);
      spool = result.spool;
      message = outcomeText(result.outcome, result.spool.state);
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
      message = `Undid “${eventTitle(event.type)}”.`;
      await load(id);
    } catch (error) {
      message = describeError(error);
    } finally {
      busy = false;
    }
  }

  async function save(changes: { location: string | null; notes: string | null }): Promise<void> {
    spool = await updateSpool(id, changes);
  }
</script>

<svelte:head><title>Spool #{page.params.id} · RollCall</title></svelte:head>

<div class="page">
  <a class="back" href="/spools">
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2.2"
      aria-hidden="true"
    >
      <path d="m15 18-6-6 6-6"></path>
    </svg>
    Spools
  </a>

  {#if failure}
    <p role="alert" class="error">{failure}</p>
  {:else if !spool}
    <p class="muted">Loading…</p>
  {:else}
    <div class="hero">
      <Ring rgba={spool.product.color_rgba} size="lg" />
      <div class="title">
        <div class="tags">
          <StateChip state={spool.state} />
          <span class="mono muted">
            Spool #{spool.id} · {spool.product.filament_type} · #{hexText(spool.product.color_rgba)}
          </span>
          {#if spool.placeholder}<span class="badge-hand">No tag yet</span>{/if}
        </div>
        <h1>{spool.product.display_name}</h1>
        <p class="muted">{statusLine(spool)}</p>
      </div>
    </div>

    {#if !canEdit && message}<p role="status">{message}</p>{/if}

    <div class="columns">
      <div class="main">
        {#if canEdit}
          <ActionCard state={spool.state} {busy} {message} onaction={act} />
        {/if}
        <History events={spool.events} canUndo={canEdit} {busy} onundo={undo} />
      </div>
      <div class="side">
        <LeftOnSpool {spool} />
        <WhereNotes {spool} {canEdit} onsave={save} />
        <TagData tags={spool.tags} />
      </div>
    </div>
  {/if}
</div>

<style>
  .back {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: var(--muted);
    font-size: 14px;
    font-weight: 600;
    min-height: 44px;
    align-self: flex-start;
  }

  .hero {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 24px;
  }

  .title {
    flex: 1 1 320px;
    min-width: 0;
  }

  .tags {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
    font-size: 13px;
  }

  h1 {
    margin-top: 8px;
  }

  .title p {
    margin: 6px 0 0;
    font-size: 15px;
  }

  .columns {
    display: flex;
    flex-wrap: wrap;
    gap: 20px;
    align-items: flex-start;
  }

  .main,
  .side {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .main {
    flex: 999 1 560px;
  }

  .side {
    flex: 1 1 320px;
  }
</style>
