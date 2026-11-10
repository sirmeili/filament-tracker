<script lang="ts">
  import { describeError } from "#lib/api/errors.ts";
  import { getInventory } from "#lib/api/stock.ts";
  import type { ProductSummary } from "#lib/api/types.ts";
  import InventoryCard from "#lib/components/inventory/InventoryCard.svelte";
  import InventoryTable from "#lib/components/inventory/InventoryTable.svelte";
  import SummaryTiles from "#lib/components/inventory/SummaryTiles.svelte";
  import {
    ALL_TYPES,
    filamentTypes,
    type InventoryView,
    savedView,
    saveView,
    totals,
    visibleProducts,
  } from "#lib/inventory.ts";

  let items = $state<ProductSummary[] | null>(null);
  let failure = $state<string | null>(null);
  let type = $state(ALL_TYPES);
  let lowFirst = $state(false);
  let view = $state<InventoryView>(savedView());

  const shown = $derived(items ? visibleProducts(items, type, lowFirst) : []);

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
    {#if items}<SummaryTiles totals={totals(items)} />{/if}
  </div>

  {#if failure}
    <p role="alert" class="error">
      {failure} <button class="small" onclick={load}>Try again</button>
    </p>
  {:else if !items}
    <p class="muted">Loading…</p>
  {:else if items.length === 0}
    <p class="muted">No products yet. Scan a spool's tag to add its product.</p>
  {:else}
    <div class="controls">
      <div class="toolbar" role="group" aria-label="Filter by type">
        {#each filamentTypes(items) as option (option)}
          <button
            type="button"
            class="chip"
            aria-pressed={type === option}
            onclick={() => (type = option)}>{option}</button
          >
        {/each}
      </div>
      <div class="toolbar">
        <button
          type="button"
          class="chip"
          aria-pressed={lowFirst}
          onclick={() => (lowFirst = !lowFirst)}
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.2"
            aria-hidden="true"
          >
            <path d="M7 4v16M3 16l4 4 4-4M14 6h7M14 12h5M14 18h3"></path>
          </svg>
          Low stock first
        </button>
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
      </div>
    </div>

    {#if view === "cards"}
      <div class="grid">
        {#each shown as item (item.product.id)}
          <InventoryCard {item} />
        {/each}
      </div>
    {:else}
      <InventoryTable items={shown} />
    {/if}
  {/if}
</div>

<style>
  .page {
    gap: 28px;
  }

  .controls {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .toolbar {
    gap: 8px 10px;
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
