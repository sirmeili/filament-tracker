<script lang="ts">
  import type { Snippet } from "svelte";
  import Ring from "#lib/components/ui/Ring.svelte";

  /** One Review item: a swatch (or a question mark for a tag with no spool), what happened,
   * and the actions. */
  interface Props {
    rgba?: string;
    title: string;
    body: string;
    meta: Snippet;
    actions?: Snippet;
  }

  let { rgba, title, body, meta, actions }: Props = $props();
</script>

<article>
  {#if rgba}
    <Ring {rgba} size="sm" />
  {:else}
    <span class="unknown" aria-hidden="true">?</span>
  {/if}
  <div class="text">
    <h3>{title}</h3>
    <p>{body}</p>
    <p class="meta">{@render meta()}</p>
  </div>
  {#if actions}<div class="actions">{@render actions()}</div>{/if}
</article>

<style>
  article {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    gap: 16px;
    padding: 18px 20px;
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 16px;
  }

  .unknown {
    width: 30px;
    height: 30px;
    flex: none;
    border-radius: 50%;
    border: 2px dashed var(--muted);
    color: var(--muted);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
  }

  .text {
    flex: 1 1 320px;
    min-width: 0;
  }

  h3 {
    margin: 0;
    font-size: 17px;
    font-weight: 600;
  }

  p {
    margin: 4px 0 0;
    font-size: 14px;
  }

  .meta {
    color: var(--muted);
    font-size: 13px;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
</style>
