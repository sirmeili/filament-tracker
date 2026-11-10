<script lang="ts">
  import type { ProductSummary } from "#lib/api/types.ts";
  import Ring from "#lib/components/ui/Ring.svelte";
  import { hexText } from "#lib/format.ts";
  import { type Draft, draftProblem, sourceText, spoolCount } from "#lib/products.ts";

  interface Props {
    items: ProductSummary[];
    /** Editable values by product ID; null shows the saved values read-only (Viewers). */
    drafts: Record<number, Draft> | null;
  }

  let { items, drafts }: Props = $props();
</script>

<div class="tablebox">
  <table>
    <thead>
      <tr>
        <th scope="col" class="name">Display name</th>
        <th scope="col">Type</th>
        <th scope="col">Color</th>
        <th scope="col">Spools</th>
        <th scope="col">Low at ≤ (sealed)</th>
        <th scope="col">Nearly out at ≤</th>
        <th scope="col">Source</th>
      </tr>
    </thead>
    <tbody>
      {#each items as item (item.product.id)}
        {@const product = item.product}
        {@const draft = drafts?.[product.id]}
        {@const problem = draft ? draftProblem(draft) : null}
        <tr>
          <td>
            <div class="named">
              <Ring rgba={product.color_rgba} size="sm" />
              {#if draft}
                <label class="grow">
                  <span class="sr-only">Display name for #{hexText(product.color_rgba)}</span>
                  <input
                    class="title"
                    type="text"
                    maxlength="100"
                    aria-invalid={problem !== null}
                    bind:value={draft.display_name}
                  />
                </label>
              {:else}
                <span class="title">{product.display_name}</span>
              {/if}
            </div>
            {#if problem}<p class="error">{problem}</p>{/if}
          </td>
          <td class="mono muted">{product.filament_type}</td>
          <td class="mono muted">#{hexText(product.color_rgba)}</td>
          <td class="mono strong">{spoolCount(item)}</td>
          <td>
            {#if draft}
              <label class="inline">
                <span class="sr-only">Low-stock threshold for {product.display_name}</span>
                <input
                  type="number"
                  min="0"
                  max="1000"
                  step="1"
                  bind:value={draft.low_stock_threshold}
                />
                {#if draft.low_stock_threshold === 0}<span class="muted small">off</span>{/if}
              </label>
            {:else}
              <span class="mono">{product.low_stock_threshold || "off"}</span>
            {/if}
          </td>
          <td>
            {#if draft}
              <label class="inline">
                <span class="sr-only">Nearly-out % for {product.display_name}</span>
                <input type="number" min="0" max="100" step="1" bind:value={draft.nearly_out_pct} />
                <span class="muted small">%</span>
              </label>
            {:else}
              <span class="mono">{product.nearly_out_pct}%</span>
            {/if}
          </td>
          <td>
            {#if product.provisional}
              <span class="badge-hand">{sourceText(product)}</span>
            {:else}
              <span class="from-tag">From tag</span>
            {/if}
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  table {
    min-width: 980px;
  }

  .name {
    width: 36%;
  }

  .named {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .grow {
    flex: 1;
    display: flex;
  }

  .grow input {
    flex: 1;
  }

  .title {
    font-family: var(--font-head);
    font-weight: 600;
  }

  .inline {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .inline input {
    width: 80px;
    font-family: var(--font-mono);
  }

  .strong {
    font-weight: 700;
  }

  .small {
    font-size: 12px;
  }

  .from-tag {
    font-size: 12px;
    font-weight: 600;
    padding: 3px 9px;
    border-radius: 6px;
    background: var(--chip);
    white-space: nowrap;
  }

  .error {
    margin: 6px 0 0 42px;
    font-size: 13px;
  }
</style>
