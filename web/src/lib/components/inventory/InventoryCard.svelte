<script lang="ts">
  import type { ProductSummary } from "#lib/api/types.ts";
  import OpenSpools from "#lib/components/inventory/OpenSpools.svelte";
  import Ring from "#lib/components/ui/Ring.svelte";
  import { hexText } from "#lib/format.ts";
  import { thresholdText } from "#lib/inventory.ts";

  let { item }: { item: ProductSummary } = $props();
  const product = $derived(item.product);
</script>

<article>
  <div class="head">
    <Ring rgba={product.color_rgba} />
    <div class="name">
      <h2>{product.display_name}</h2>
      <div class="meta mono">
        <span>{product.filament_type}</span><span aria-hidden="true">·</span><span
          >#{hexText(product.color_rgba)}</span
        >
      </div>
    </div>
    {#if item.low_stock}<span class="badge-low">LOW</span>{/if}
  </div>
  <dl class="counts">
    <!-- Label first for screen readers; shown below the number. -->
    <div>
      <dt>Sealed</dt>
      <dd>{item.counts.sealed}</dd>
    </div>
    <div>
      <dt>Open</dt>
      <dd>{item.counts.open}</dd>
    </div>
    <div class="used">
      <dt>Used up</dt>
      <dd>{item.counts.empty}</dd>
    </div>
  </dl>
  {#if item.open_spools.length}
    <div class="open">
      <h3 class="label">Open spools · left</h3>
      <OpenSpools spools={item.open_spools} />
    </div>
  {/if}
  <div class="foot">
    <span>{thresholdText(product.low_stock_threshold)}</span>
    {#if product.provisional}<span class="badge-hand">Added by hand</span>{/if}
  </div>
</article>

<style>
  article {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 18px;
  }

  .head {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .name {
    flex: 1;
    min-width: 0;
  }

  h2 {
    margin: 0;
    font-size: 19px;
    font-weight: 600;
    line-height: 1.25;
  }

  .meta {
    margin-top: 4px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    font-size: 13px;
    color: var(--muted);
  }

  .badge-low {
    align-self: flex-start;
  }

  .counts {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    margin: 0;
    border: 1px solid var(--line);
    border-radius: 10px;
    overflow: hidden;
  }

  .counts div {
    display: flex;
    flex-direction: column-reverse;
    padding: 10px 12px;
    border-right: 1px solid var(--line);
  }

  .counts div:last-child {
    border-right: 0;
  }

  dd {
    margin: 0;
    font-family: var(--font-mono);
    font-size: 24px;
    font-weight: 700;
  }

  dt {
    font-size: 12px;
    color: var(--muted);
    font-weight: 500;
  }

  .used dd {
    color: var(--muted);
  }

  .open {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .foot {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--muted);
    margin-top: auto;
  }
</style>
