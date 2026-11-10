<script lang="ts">
  // The Cards view's totals, one line above the cards: "All 11 · 14 sealed · 9 open · 23 used".
  import type { Totals } from "#lib/inventory.ts";

  let { totals, countText }: { totals: Totals; countText: string } = $props();
</script>

<p class="totals">
  <strong>{countText}</strong>
  <span>{totals.sealed} sealed</span>
  <span>{totals.open} open</span>
  <span class="muted">{totals.empty} used</span>
</p>

<style>
  .totals {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 16px;
    margin: 0;
    font-size: 14px;
  }

  span {
    font-family: var(--font-mono);
    font-weight: 600;
  }
</style>
