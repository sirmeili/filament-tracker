<script lang="ts">
  // Inventory's filter sheet (docs/mockups/mobile-web/PhoneFilterSheet.dc.html): types, Low
  // stock only and the sort. Changes apply on "Show N products"; Escape, the dimmed page or
  // Close leave the filter as it was. It rises from the bottom on a phone and is a centred
  // panel on wider screens.
  import type { ProductSummary } from "#lib/api/types.ts";
  import { applyFilter, type InventoryFilter, noFilter, SORTS } from "#lib/inventory.ts";

  interface Props {
    items: ProductSummary[];
    /** The filament types on hand with their product counts, most common first. */
    types: { type: string; count: number }[];
    filter: InventoryFilter;
    onapply: (filter: InventoryFilter) => void;
    onclose: () => void;
  }

  let { items, types, filter, onapply, onclose }: Props = $props();

  // The sheet edits a copy; the page's filter changes only on Show.
  // svelte-ignore state_referenced_locally
  let draft = $state<InventoryFilter>({ ...filter, types: [...filter.types] });
  const count = $derived(applyFilter(items, draft).length);

  let sheet: HTMLDivElement;

  $effect(() => {
    sheet.querySelector<HTMLElement>("button")?.focus();
  });

  function toggleType(type: string): void {
    draft.types = draft.types.includes(type)
      ? draft.types.filter((t) => t !== type)
      : [...draft.types, type];
  }

  function clear(): void {
    draft = { ...noFilter(), query: draft.query, sort: draft.sort };
  }

  /** Escape closes; Tab stays inside the sheet. */
  function keydown(event: KeyboardEvent): void {
    if (event.key === "Escape") {
      event.preventDefault();
      onclose();
      return;
    }
    if (event.key !== "Tab") return;
    const all = [...sheet.querySelectorAll<HTMLElement>("button, input")];
    const first = all[0];
    const last = all[all.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
</script>

<button type="button" class="dim" aria-label="Close the filters" tabindex="-1" onclick={onclose}
></button>
<div
  class="sheet"
  role="dialog"
  aria-modal="true"
  aria-labelledby="filter-h"
  tabindex="-1"
  bind:this={sheet}
  onkeydown={keydown}
>
  <span class="grip" aria-hidden="true"></span>
  <div class="head">
    <h2 id="filter-h">Filter</h2>
    <button type="button" class="small" onclick={onclose}>Close</button>
  </div>

  <section aria-labelledby="type-h">
    <h3 id="type-h" class="label">Type</h3>
    <div class="chips" role="group" aria-labelledby="type-h">
      {#each types as entry (entry.type)}
        <button
          type="button"
          class="chip"
          aria-pressed={draft.types.includes(entry.type)}
          onclick={() => toggleType(entry.type)}
          >{entry.type} <span class="n">{entry.count}</span></button
        >
      {/each}
    </div>
  </section>

  <section aria-labelledby="show-h">
    <h3 id="show-h" class="label">Show</h3>
    <label class="check">
      <input type="checkbox" bind:checked={draft.lowOnly} />
      Low stock only
    </label>
  </section>

  <section aria-labelledby="sort-h">
    <h3 id="sort-h" class="label">Sort</h3>
    <div class="seg" role="group" aria-labelledby="sort-h">
      {#each SORTS as sort (sort.value)}
        <button
          type="button"
          aria-pressed={draft.sort === sort.value}
          onclick={() => (draft.sort = sort.value)}>{sort.label}</button
        >
      {/each}
    </div>
  </section>

  <div class="foot">
    <button type="button" onclick={clear}>Clear</button>
    <button type="button" class="primary" onclick={() => onapply(draft)}>
      Show {count}
      {count === 1 ? "product" : "products"}
    </button>
  </div>
</div>

<style>
  .dim {
    position: fixed;
    inset: 0;
    z-index: 50;
    border: 0;
    border-radius: 0;
    padding: 0;
    min-height: 0;
    background: rgba(0, 0, 0, 0.45);
  }

  .sheet {
    position: fixed;
    z-index: 51;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    width: min(480px, calc(100vw - 32px));
    max-height: calc(100dvh - 48px);
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 18px;
    padding: 18px 20px 20px;
    border-radius: 20px;
    background: var(--surface);
    box-sizing: border-box;
    outline: none;
  }

  .grip {
    display: none;
  }

  @media (max-width: 600px) {
    .sheet {
      left: 0;
      right: 0;
      top: auto;
      bottom: 0;
      transform: none;
      width: auto;
      padding: 10px 16px calc(18px + env(safe-area-inset-bottom, 0px));
      border-radius: 24px 24px 0 0;
    }

    .grip {
      display: block;
      align-self: center;
      width: 40px;
      height: 5px;
      border-radius: 999px;
      background: var(--line);
    }
  }

  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  h2,
  h3 {
    margin: 0;
  }

  h2 {
    font-size: 20px;
  }

  section {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .n {
    margin-left: 4px;
    font-family: var(--font-mono);
    font-size: 12px;
    opacity: 0.75;
  }

  .check {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 44px;
    font-weight: 600;
  }

  .check input {
    width: 20px;
    height: 20px;
    min-height: 0;
  }

  .seg {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 4px;
    padding: 4px;
    border-radius: 12px;
    background: var(--chip);
  }

  .seg button {
    border: 0;
    background: transparent;
    color: var(--muted);
  }

  .seg button[aria-pressed="true"] {
    background: var(--surface);
    color: var(--text);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.18);
  }

  .foot {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 10px;
  }
</style>
