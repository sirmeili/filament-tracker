<script lang="ts">
  // Inventory on a phone (docs/mockups/mobile-web/PhoneInventory-Filter.dc.html): a header with
  // the totals, then one compact row per product that expands in place, one at a time.
  import type { ProductSummary } from "#lib/api/types.ts";
  import ProductDetail from "#lib/components/inventory/ProductDetail.svelte";
  import Ring from "#lib/components/ui/Ring.svelte";
  import { hexText } from "#lib/format.ts";
  import type { Totals } from "#lib/inventory.ts";

  interface Props {
    items: ProductSummary[];
    totals: Totals;
    /** "All 11" or "5 of 11". */
    countText: string;
  }

  let { items, totals, countText }: Props = $props();

  let expanded = $state<number | null>(null);
</script>

<div class="list">
  <div class="row header">
    <span class="count">{countText}</span>
    <span class="num"><span class="label">Sealed</span><span>{totals.sealed}</span></span>
    <span class="num"><span class="label">Open</span><span>{totals.open}</span></span>
    <span class="num used"><span class="label">Used</span><span>{totals.empty}</span></span>
    <span class="chev"></span>
  </div>
  <ul>
    {#each items as item (item.product.id)}
      {@const product = item.product}
      {@const open = expanded === product.id}
      <li class:open>
        <button
          type="button"
          class="row"
          aria-expanded={open}
          aria-controls="detail-{product.id}"
          onclick={() => (expanded = open ? null : product.id)}
        >
          <span class="prod">
            <Ring rgba={product.color_rgba} size="sm" />
            <span class="text">
              <span class="name">{product.display_name}</span>
              <span class="meta mono">
                {#if item.low_stock}<span class="badge-low">LOW</span>{/if}
                {product.filament_type} · #{hexText(product.color_rgba)}
              </span>
            </span>
          </span>
          <span class="num" aria-label="{item.counts.sealed} sealed">{item.counts.sealed}</span>
          <span class="num" aria-label="{item.counts.open} open">{item.counts.open}</span>
          <span class="num used" aria-label="{item.counts.empty} used up">{item.counts.empty}</span>
          <svg
            class="chev"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.4"
            aria-hidden="true"
          >
            <path d="M6 9l6 6 6-6"></path>
          </svg>
        </button>
        {#if open}
          <div id="detail-{product.id}">
            <ProductDetail {item} />
          </div>
        {/if}
      </li>
    {/each}
  </ul>
</div>

<style>
  .list {
    border: 1px solid var(--line);
    border-radius: 14px;
    background: var(--surface);
    overflow: hidden;
  }

  ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 40px 40px 40px 18px;
    align-items: center;
    gap: 4px;
    width: 100%;
    padding: 10px 12px;
    box-sizing: border-box;
    text-align: left;
  }

  button.row {
    min-height: 64px;
    border: 0;
    border-top: 1px solid var(--line);
    border-radius: 0;
    background: transparent;
    font-weight: 400;
  }

  .header {
    padding-top: 8px;
    padding-bottom: 8px;
  }

  .count {
    font-weight: 700;
    font-size: 13px;
  }

  .num {
    display: flex;
    flex-direction: column;
    align-items: center;
    font-family: var(--font-mono);
    font-size: 16px;
    font-weight: 700;
  }

  .header .num .label {
    font-family: var(--font-body);
    font-size: 10px;
  }

  .used {
    color: var(--muted);
  }

  .prod {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }

  .text {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .name {
    font-family: var(--font-head);
    font-size: 15px;
    font-weight: 600;
    line-height: 1.25;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .meta {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--muted);
  }

  .meta .badge-low {
    font-size: 10px;
    padding: 1px 6px;
  }

  .chev {
    color: var(--muted);
    transition: transform 0.15s;
  }

  li.open .chev {
    transform: rotate(180deg);
  }

  li.open {
    background: var(--bg);
  }
</style>
