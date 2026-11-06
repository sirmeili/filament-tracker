<script lang="ts">
  import Ring from "#lib/components/ui/Ring.svelte";
  import { stateText } from "#lib/phone/card-text.ts";
  import type { Card } from "#lib/phone/scan-flow.ts";

  let { card }: { card: Card } = $props();
</script>

<article class="card" aria-label="Spool">
  {#if card.colorRgba}
    <Ring rgba={card.colorRgba} />
  {/if}
  <div>
    <h2>
      {#if card.spoolId}<a href="/spools/{card.spoolId}">{card.name}</a>{:else}{card.name}{/if}
    </h2>
    <p class="muted">{stateText(card)}</p>
    {#if card.remainingPct !== null}
      <p class="muted">{card.remainingPct}% left, as the AMS last reported</p>
    {/if}
  </div>
</article>

<style>
  .card {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 20px;
    border-radius: 16px;
    background: var(--surface);
    border: 1px solid var(--line);
  }

  h2 {
    margin: 0 0 4px;
    font-size: 20px;
  }

  p {
    margin: 0;
  }
</style>
