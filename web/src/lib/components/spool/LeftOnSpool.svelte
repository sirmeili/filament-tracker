<script lang="ts">
  import type { SpoolDetail } from "#lib/api/types.ts";
  import { nearlyOut } from "#lib/spools.ts";

  /** The AMS remaining % and grams left. Empty until the AMS reports (M5). */
  let { spool }: { spool: SpoolDetail } = $props();

  const low = $derived(nearlyOut(spool));
</script>

<section class="card" aria-labelledby="ams-h">
  <h2 id="ams-h" class="label">Left on spool</h2>
  {#if spool.remaining_pct === null}
    <p class="muted">
      Not seen by the AMS yet. The % and grams left appear once a printer reports this spool.
    </p>
    {#if spool.spool_weight_g}<p class="muted">Full spool: {spool.spool_weight_g} g</p>{/if}
  {:else}
    <div class="big">
      <span class="pct" class:low>{spool.remaining_pct}%</span>
      {#if spool.grams_left !== null}
        <span class="muted">about {spool.grams_left} g of {spool.spool_weight_g} g</span>
      {/if}
    </div>
    <div class="track" aria-hidden="true">
      <span class:low style:width="{Math.max(0, Math.min(100, spool.remaining_pct))}%"></span>
    </div>
    {#if low}<p class="notice">Nearly out (at or below {spool.product.nearly_out_pct}%).</p>{/if}
  {/if}
</section>

<style>
  p {
    margin: 0;
    font-size: 14px;
  }

  .big {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 8px;
    font-size: 14px;
  }

  .pct {
    font-family: var(--font-mono);
    font-size: 48px;
    font-weight: 700;
    line-height: 1;
  }

  .pct.low {
    color: var(--lowtext);
  }

  .track {
    height: 10px;
    border-radius: 999px;
    background: var(--track);
    overflow: hidden;
  }

  .track span {
    display: block;
    height: 100%;
    border-radius: 999px;
    background: var(--fill);
  }

  .track span.low {
    background: var(--fillLow);
  }
</style>
