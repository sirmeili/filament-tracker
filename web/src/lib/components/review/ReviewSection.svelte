<script lang="ts">
  import type { Snippet } from "svelte";

  /** One Review section: a heading with a count, the items, or a note when there are none. */
  interface Props {
    id: string;
    title: string;
    count: number;
    empty: string;
    children: Snippet;
  }

  let { id, title, count, empty, children }: Props = $props();
</script>

<section aria-labelledby={id}>
  <h2 {id}>{title} <span class="count">{count}</span></h2>
  {#if count === 0}
    <p class="muted">{empty}</p>
  {:else}
    <div class="items">{@render children()}</div>
  {/if}
</section>

<style>
  section {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  h2 {
    margin: 0;
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 22px;
    font-weight: 600;
  }

  .count {
    font-family: var(--font-mono);
    font-size: 13px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 999px;
    background: var(--chip);
  }

  .items {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  p {
    margin: 0;
  }
</style>
