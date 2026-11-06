<script lang="ts">
  import type { SpoolRow } from "#lib/api/types.ts";
  import PctBar from "#lib/components/ui/PctBar.svelte";
  import Ring from "#lib/components/ui/Ring.svelte";
  import StateChip from "#lib/components/ui/StateChip.svelte";
  import { shortDate } from "#lib/format.ts";
  import { slotText } from "#lib/printers.ts";
  import { nearlyOut } from "#lib/spools.ts";

  interface Props {
    spools: SpoolRow[];
    /** Spool IDs ticked for a bulk move; null hides the checkboxes (Viewers). */
    selected: Set<number> | null;
    ontoggle?: (id: number) => void;
  }

  let { spools, selected, ontoggle }: Props = $props();
</script>

<div class="tablebox">
  <table>
    <thead>
      <tr>
        {#if selected}<th scope="col" class="pick"><span class="sr-only">Select</span></th>{/if}
        <th scope="col">Product</th>
        <th scope="col">State</th>
        <th scope="col">Location</th>
        <th scope="col" class="left">Left</th>
        <th scope="col">Received</th>
        <th scope="col">Opened</th>
        <th scope="col">Used up</th>
      </tr>
    </thead>
    <tbody>
      {#each spools as spool (spool.id)}
        <tr class:sel={selected?.has(spool.id)}>
          {#if selected}
            <td>
              <input
                type="checkbox"
                aria-label="Select spool {spool.id}"
                checked={selected.has(spool.id)}
                onchange={() => ontoggle?.(spool.id)}
              />
            </td>
          {/if}
          <td>
            <a class="prod" href="/spools/{spool.id}">
              <Ring rgba={spool.product.color_rgba} size="sm" />
              <span>
                <span class="name">{spool.product.display_name}</span>
                <span class="sub mono"
                  >#{spool.id}{#if spool.placeholder}&nbsp;· no tag yet{/if}</span
                >
              </span>
            </a>
          </td>
          <td><StateChip state={spool.state} /></td>
          <td>
            {spool.location ?? (spool.ams_slot ? "" : "—")}
            {#if spool.ams_slot}
              <span class="sub">{slotText(spool.ams_slot)}</span>
            {/if}
          </td>
          <td>
            {#if spool.state === "open"}
              <PctBar pct={spool.remaining_pct} low={nearlyOut(spool)} />
            {:else}
              <span class="muted">—</span>
            {/if}
          </td>
          <td class="date">{shortDate(spool.received_at)}</td>
          <td class="date">{shortDate(spool.opened_at)}</td>
          <td class="date">{shortDate(spool.emptied_at)}</td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  table {
    min-width: 940px;
  }

  .pick {
    width: 20px;
  }

  .left {
    width: 170px;
  }

  tr.sel td {
    background: var(--chip);
  }

  .prod {
    display: flex;
    align-items: center;
    gap: 12px;
    min-height: 44px;
  }

  .name {
    display: block;
    font-family: var(--font-head);
    font-weight: 600;
    font-size: 15px;
  }

  .sub {
    display: block;
    font-size: 12px;
    color: var(--muted);
  }

  .date {
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--muted);
    white-space: nowrap;
  }
</style>
