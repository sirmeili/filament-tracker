<script lang="ts">
  import type { Totals } from "#lib/inventory.ts";

  let { totals }: { totals: Totals } = $props();
</script>

<ul class="tiles" aria-label="Totals">
  <li><span class="n">{totals.sealed}</span><span class="t">Sealed</span></li>
  <li><span class="n">{totals.open}</span><span class="t">Open</span></li>
  <li><span class="n">{totals.nearlyOut}</span><span class="t">Open, nearly out</span></li>
  <li class="low"><span class="n">{totals.lowStock}</span><span class="t">Low on stock</span></li>
</ul>

<style>
  .tiles {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: flex;
    flex-direction: column;
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 12px 18px;
    min-width: 110px;
  }

  .n {
    font-family: var(--font-mono);
    font-size: 28px;
    font-weight: 700;
  }

  .t {
    font-size: 13px;
    color: var(--muted);
    font-weight: 500;
  }

  .low {
    background: var(--lowbg);
    border-color: var(--lowbg);
    color: var(--lowtext);
  }

  .low .t {
    color: var(--lowtext);
    font-weight: 600;
  }
</style>
