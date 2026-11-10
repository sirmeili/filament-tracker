<script lang="ts">
  // Inventory's search, Filter button and quick filters, at every screen size
  // (docs/mockups/mobile-web/PhoneInventory-Filter.dc.html).
  import {
    activeFilters,
    chosenTypes,
    type InventoryFilter,
    noFilter,
    type Totals,
    typeSummary,
  } from "#lib/inventory.ts";

  interface Props {
    filter: InventoryFilter;
    /** The filament types on hand, most common first. */
    types: string[];
    totals: Totals;
    /** Opens the filter sheet. */
    onopen: () => void;
  }

  let { filter = $bindable(), types, totals, onopen }: Props = $props();

  const active = $derived(activeFilters(filter, types));
  const typeText = $derived(typeSummary(chosenTypes(filter.types, types), types));

  function clear(): void {
    filter = { ...noFilter(), query: filter.query, sort: filter.sort };
  }
</script>

<div class="controls">
  <div class="top">
    <label class="search">
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.2"
        aria-hidden="true"
      >
        <circle cx="11" cy="11" r="7"></circle>
        <path d="M20 20l-3.5-3.5"></path>
      </svg>
      <input
        type="search"
        aria-label="Search name or color"
        placeholder="Search name or color"
        bind:value={filter.query}
      />
    </label>
    <button
      type="button"
      class="filter"
      class:on={active > 0}
      aria-haspopup="dialog"
      aria-label={active > 0 ? `Filter, ${active} on` : "Filter"}
      onclick={onopen}
    >
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.2"
        stroke-linecap="round"
        aria-hidden="true"
      >
        <path d="M4 6h16M7 12h10M10 18h4"></path>
      </svg>
      Filter
      {#if active > 0}<span class="count" aria-hidden="true">{active}</span>{/if}
    </button>
  </div>

  <div class="quick" role="group" aria-label="Quick filters">
    <button
      type="button"
      class="chip"
      aria-pressed={filter.lowOnly}
      onclick={() => (filter.lowOnly = !filter.lowOnly)}
    >
      Low stock <span class="n">{totals.lowStock}</span>
    </button>
    <button
      type="button"
      class="chip"
      aria-pressed={filter.nearlyOnly}
      onclick={() => (filter.nearlyOnly = !filter.nearlyOnly)}
    >
      Nearly out <span class="n">{totals.nearlyOut}</span>
    </button>
    {#if typeText}
      <span class="typechip">
        <button type="button" class="label-button" onclick={onopen}>{typeText}</button>
        <button
          type="button"
          class="x"
          aria-label="Clear the types"
          onclick={() => (filter.types = [])}>✕</button
        >
      </span>
    {/if}
    {#if active > 0}
      <button type="button" class="clear" onclick={clear}>Clear</button>
    {/if}
  </div>
</div>

<style>
  .controls {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .top {
    display: flex;
    gap: 8px;
  }

  .search {
    position: relative;
    flex: 1;
    max-width: 420px;
  }

  .search svg {
    position: absolute;
    left: 12px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--muted);
  }

  .search input {
    width: 100%;
    padding-left: 38px;
    box-sizing: border-box;
  }

  .filter {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .filter.on {
    background: var(--text);
    border-color: var(--text);
    color: var(--bg);
  }

  .count {
    min-width: 20px;
    padding: 0 6px;
    border-radius: 999px;
    background: var(--accent);
    color: var(--onaccent);
    font-size: 12px;
    font-weight: 700;
    text-align: center;
  }

  .quick {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }

  .n {
    margin-left: 4px;
    padding: 0 7px;
    border-radius: 999px;
    background: var(--lowbg);
    color: var(--lowtext);
    font-size: 12px;
    font-weight: 700;
  }

  .typechip {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    background: var(--text);
    color: var(--bg);
  }

  .typechip button {
    min-height: 40px;
    border: 0;
    background: transparent;
    color: inherit;
    font-weight: 600;
  }

  .label-button {
    padding: 0 4px 0 14px;
  }

  .x {
    padding: 0 12px 0 6px;
  }

  .clear {
    border: 0;
    background: transparent;
    color: var(--muted);
    text-decoration: underline;
  }
</style>
