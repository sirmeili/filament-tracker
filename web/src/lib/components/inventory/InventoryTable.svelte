<script lang="ts">
  import type { ProductSummary } from "#lib/api/types.ts";
  import OpenSpools from "#lib/components/inventory/OpenSpools.svelte";
  import Ring from "#lib/components/ui/Ring.svelte";
  import { hexText } from "#lib/format.ts";

  let { items }: { items: ProductSummary[] } = $props();
</script>

<div class="tablebox">
  <table>
    <thead>
      <tr>
        <th scope="col">Product</th>
        <th scope="col">Type</th>
        <th scope="col" class="num">Sealed</th>
        <th scope="col" class="num">Open</th>
        <th scope="col" class="num">Used up</th>
        <th scope="col" class="spools">Open spools · left</th>
        <th scope="col">Status</th>
      </tr>
    </thead>
    <tbody>
      {#each items as item (item.product.id)}
        {@const product = item.product}
        <tr>
          <th scope="row">
            <span class="prod">
              <Ring rgba={product.color_rgba} size="sm" />
              <span>
                <span class="name">{product.display_name}</span>
                <span class="hex mono">#{hexText(product.color_rgba)}</span>
              </span>
            </span>
          </th>
          <td class="mono muted">{product.filament_type}</td>
          <td class="num">{item.counts.sealed}</td>
          <td class="num">{item.counts.open}</td>
          <td class="num muted">{item.counts.empty}</td>
          <td>
            {#if item.open_spools.length}
              <OpenSpools spools={item.open_spools} />
            {:else}
              <span class="muted">—</span>
            {/if}
          </td>
          <td class="status">
            {#if item.low_stock}
              <span class="badge-low">LOW · ≤{product.low_stock_threshold}</span>
            {:else}
              <span class="muted">{product.low_stock_threshold > 0 ? "OK" : "Alert off"}</span>
            {/if}
            {#if product.provisional}<span class="badge-hand">By hand</span>{/if}
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  table {
    min-width: 860px;
  }

  th[scope="row"] {
    text-transform: none;
    letter-spacing: normal;
    color: inherit;
    font-size: 14px;
    border-bottom: 1px solid var(--line);
    padding: 14px 16px;
  }

  tbody tr:last-child th {
    border-bottom: 0;
  }

  .prod {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .name {
    display: block;
    font-family: var(--font-head);
    font-weight: 600;
    font-size: 16px;
  }

  .hex {
    display: block;
    font-size: 12px;
    font-weight: 400;
    color: var(--muted);
  }

  .num {
    text-align: right;
    font-family: var(--font-mono);
    font-weight: 700;
    font-size: 16px;
  }

  th.num {
    font-family: var(--font-body);
    font-size: 12px;
    font-weight: 600;
  }

  .spools {
    width: 230px;
  }

  .status {
    white-space: nowrap;
  }

  .status .badge-hand {
    margin-left: 6px;
  }
</style>
