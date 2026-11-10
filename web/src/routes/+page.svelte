<script lang="ts">
  import { describeError } from "#lib/api/errors.ts";
  import { getInventory } from "#lib/api/stock.ts";
  import type { ProductSummary } from "#lib/api/types.ts";
  import CompactList from "#lib/components/inventory/CompactList.svelte";
  import FilterSheet from "#lib/components/inventory/FilterSheet.svelte";
  import InventoryCard from "#lib/components/inventory/InventoryCard.svelte";
  import InventoryControls from "#lib/components/inventory/InventoryControls.svelte";
  import InventoryTable from "#lib/components/inventory/InventoryTable.svelte";
  import TotalsLine from "#lib/components/inventory/TotalsLine.svelte";
  import {
    applyFilter,
    type InventoryFilter,
    type InventoryView,
    noFilter,
    onHand,
    savedView,
    saveView,
    shownText,
    totals,
    typeCounts,
  } from "#lib/inventory.ts";
  import { viewport } from "#lib/viewport.svelte.ts";

  let items = $state<ProductSummary[] | null>(null);
  let failure = $state<string | null>(null);
  let filter = $state<InventoryFilter>(noFilter());
  let sheetOpen = $state(false);
  let view = $state<InventoryView>(savedView());

  const screen = viewport();
  const all = $derived(items ? onHand(items) : []);
  const shown = $derived(items ? applyFilter(items, filter) : []);
  const types = $derived(items ? typeCounts(items) : []);
  const sum = $derived(totals(all));
  const countText = $derived(shownText(shown.length, all.length));

  async function load(): Promise<void> {
    failure = null;
    try {
      items = await getInventory();
    } catch (error) {
      failure = describeError(error);
    }
  }

  function show(next: InventoryView): void {
    view = next;
    saveView(next);
  }

  function apply(next: InventoryFilter): void {
    filter = next;
    sheetOpen = false;
  }

  $effect(() => {
    void load();
  });
</script>

<svelte:head><title>Inventory · RollCall</title></svelte:head>

<div class="page">
  <div class="pagehead">
    <div>
      <h1>Inventory</h1>
      <p>Every product on hand, by spool state.</p>
    </div>
  </div>

  {#if failure}
    <p role="alert" class="error">
      {failure} <button class="small" onclick={load}>Try again</button>
    </p>
  {:else if !items}
    <p class="muted">Loading…</p>
  {:else if items.length === 0}
    <p class="muted">No products yet. Scan a spool's tag to add its product.</p>
  {:else if all.length === 0}
    <p class="muted">Nothing on hand. Used-up spools are still on the Spools page.</p>
  {:else}
    <div class="controls">
      <InventoryControls
        bind:filter
        types={types.map((entry) => entry.type)}
        totals={sum}
        onopen={() => (sheetOpen = true)}
      />
      {#if !screen.phone}
        <div class="seg" role="group" aria-label="View">
          <button type="button" aria-pressed={view === "cards"} onclick={() => show("cards")}>
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2.2"
              aria-hidden="true"
            >
              <rect x="3" y="3" width="7" height="7" rx="1.5"></rect>
              <rect x="14" y="3" width="7" height="7" rx="1.5"></rect>
              <rect x="3" y="14" width="7" height="7" rx="1.5"></rect>
              <rect x="14" y="14" width="7" height="7" rx="1.5"></rect>
            </svg>
            Cards
          </button>
          <button type="button" aria-pressed={view === "list"} onclick={() => show("list")}>
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2.2"
              aria-hidden="true"
            >
              <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"></path>
            </svg>
            List
          </button>
        </div>
      {/if}
    </div>

    {#if shown.length === 0}
      <p class="muted">
        No products match.
        <button type="button" class="small" onclick={() => (filter = noFilter())}
          >Clear filters</button
        >
      </p>
    {:else if screen.phone}
      <CompactList items={shown} totals={sum} {countText} />
    {:else if view === "cards"}
      <TotalsLine totals={sum} {countText} />
      <div class="grid">
        {#each shown as item (item.product.id)}
          <InventoryCard {item} />
        {/each}
      </div>
    {:else}
      <InventoryTable items={shown} totals={sum} {countText} />
    {/if}
  {/if}
</div>

{#if sheetOpen && items}
  <FilterSheet {items} {types} {filter} onapply={apply} onclose={() => (sheetOpen = false)} />
{/if}

<style>
  .page {
    gap: 20px;
  }

  .controls {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
  }

  .controls > :global(:first-child) {
    flex: 1;
  }

  .seg {
    display: inline-flex;
    gap: 2px;
    padding: 2px;
    border: 1px solid var(--line);
    border-radius: 10px;
    background: var(--surface);
  }

  .seg button {
    min-height: 40px;
    padding: 0 14px;
    border: 0;
    border-radius: 8px;
    background: transparent;
    color: var(--muted);
  }

  .seg button[aria-pressed="true"] {
    background: var(--text);
    color: var(--bg);
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
  }
</style>
