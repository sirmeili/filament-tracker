<script lang="ts">
  // A compact Inventory row's detail: each open spool's % left, the low-stock rule and
  // status, where the product came from, and links to its spools and to Products.
  import type { ProductSummary } from "#lib/api/types.ts";
  import PctBar from "#lib/components/ui/PctBar.svelte";
  import { spoolsLink, statusText, thresholdText } from "#lib/inventory.ts";

  let { item }: { item: ProductSummary } = $props();
  const product = $derived(item.product);
</script>

<div class="detail">
  <div class="spools">
    <h3 class="label">Open spools · left</h3>
    {#each item.open_spools as spool (spool.id)}
      <a href="/spools/{spool.id}" class="bar">
        <PctBar pct={spool.remaining_pct} low={spool.nearly_out} />
      </a>
    {:else}
      <span class="muted">None open</span>
    {/each}
  </div>
  <dl>
    <div>
      <dt>Low-stock rule</dt>
      <dd>{thresholdText(product.low_stock_threshold)}</dd>
    </div>
    <div>
      <dt>Status</dt>
      <dd>
        {#if item.low_stock}
          <span class="badge-low">{statusText(item)}</span>
        {:else}
          {statusText(item)}
        {/if}
      </dd>
    </div>
    <div>
      <dt>Source</dt>
      <dd>{product.provisional ? "Added by hand" : "From tag"}</dd>
    </div>
  </dl>
  <div class="actions">
    <a class="button" href={spoolsLink(product.display_name)}>View spools</a>
    <a class="button" href="/products">Edit product</a>
  </div>
</div>

<style>
  .detail {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 4px 12px 14px 54px;
  }

  h3 {
    margin: 0;
  }

  .spools {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .bar {
    display: flex;
    align-items: center;
    min-height: 28px;
  }

  dl {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
    margin: 0;
  }

  dt {
    font-size: 11px;
    color: var(--muted);
  }

  dd {
    margin: 2px 0 0;
    font-size: 13px;
    font-weight: 600;
  }

  .actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
</style>
