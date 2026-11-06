<script lang="ts">
  import Ring from "#lib/components/ui/Ring.svelte";
  import { cardLine, chipKind, chipText } from "#lib/phone/card-text.ts";
  import type { Card } from "#lib/phone/scan-flow.ts";

  /** The scanned spool, large: color ring, state chip, name and when it reached its state. */
  let { card, done = false }: { card: Card; done?: boolean } = $props();
</script>

<article class="card" aria-label="Spool">
  <div class="ring">
    <Ring rgba={card.colorRgba ?? "00000000"} size="xl" />
    {#if done}
      <span class="check" aria-hidden="true">
        <svg
          width="26"
          height="26"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="3"
          stroke-linecap="round"
          stroke-linejoin="round"><path d="M20 6 9 17l-5-5"></path></svg
        >
      </span>
    {/if}
  </div>
  {#if !done}
    <div class="text">
      <span class="st {chipKind(card)}">{chipText(card)}</span>
      <h2>{card.name}</h2>
      <p class="muted">{cardLine(card)}</p>
    </div>
  {/if}
</article>

<style>
  .card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 20px;
    text-align: center;
  }

  .ring {
    position: relative;
    display: flex;
  }

  .check {
    position: absolute;
    right: -6px;
    bottom: -6px;
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: var(--okdot);
    color: #ffffff;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .text {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }

  h2 {
    margin: 0;
    font-size: 30px;
    font-weight: 700;
    line-height: 1.15;
  }

  p {
    margin: 0;
    font-size: 16px;
  }

  .st {
    display: inline-flex;
    font-size: 12px;
    font-weight: 700;
    padding: 3px 9px;
    border-radius: 6px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border: 1px solid transparent;
  }

  .st.sealed {
    background: var(--text);
    color: var(--bg);
  }

  .st.open {
    background: var(--chip);
    color: var(--text);
    border-color: var(--line);
  }

  .st.empty,
  .st.unknown,
  .st.new {
    color: var(--muted);
    border: 1px dashed var(--muted);
  }
</style>
