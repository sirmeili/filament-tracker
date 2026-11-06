<script lang="ts">
  import { describeError } from "#lib/api/errors.ts";
  import type { SpoolDetail } from "#lib/api/types.ts";
  import { slotText } from "#lib/printers.ts";

  interface Props {
    spool: SpoolDetail;
    canEdit: boolean;
    onsave: (changes: { location: string | null; notes: string | null }) => Promise<void>;
  }

  let { spool, canEdit, onsave }: Props = $props();

  // Edited copies, reset when another spool is shown.
  let location = $state("");
  let notes = $state("");
  let busy = $state(false);
  let message = $state<string | null>(null);

  $effect.pre(() => {
    location = spool.location ?? "";
    notes = spool.notes ?? "";
  });

  const dirty = $derived(location !== (spool.location ?? "") || notes !== (spool.notes ?? ""));

  async function save(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    busy = true;
    message = null;
    try {
      await onsave({ location: location.trim() || null, notes: notes.trim() || null });
      message = "Saved";
    } catch (error) {
      message = describeError(error);
    } finally {
      busy = false;
    }
  }
</script>

<section class="card" aria-labelledby="det-h">
  <h2 id="det-h" class="label">Where and notes</h2>
  {#if spool.ams_slot}
    <p class="loaded">Loaded in {slotText(spool.ams_slot)}</p>
  {/if}
  {#if canEdit}
    <form onsubmit={save}>
      <label>Location<input type="text" maxlength="100" bind:value={location} /></label>
      <label>Notes<textarea maxlength="2000" bind:value={notes}></textarea></label>
      <div class="row">
        <button type="submit" disabled={busy || !dirty}>Save</button>
        {#if message}<span role="status" class="muted">{message}</span>{/if}
      </div>
    </form>
  {:else}
    <dl>
      <dt>Location</dt>
      <dd>{spool.location ?? "—"}</dd>
      <dt>Notes</dt>
      <dd class="notes">{spool.notes ?? "—"}</dd>
    </dl>
  {/if}
</section>

<style>
  .loaded {
    margin: 0 0 12px;
    font-weight: 600;
  }

  form,
  dl {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin: 0;
  }

  label,
  dt {
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 13px;
    font-weight: 600;
    color: var(--muted);
  }

  dd {
    margin: -8px 0 0;
  }

  .notes {
    white-space: pre-wrap;
  }

  .row {
    display: flex;
    align-items: center;
    gap: 12px;
  }
</style>
