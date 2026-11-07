<script lang="ts">
  import { chipKind, chipText } from "#lib/phone/card-text.ts";
  import type { Card } from "#lib/phone/scan-flow.ts";

  /** The scanned spool's state chip; dashed for a tag not tracked yet. */
  let { card }: { card: Card } = $props();
</script>

<span class="st {chipKind(card)}">{chipText(card)}</span>

<style>
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

  .sealed {
    background: var(--text);
    color: var(--bg);
  }

  .open {
    background: var(--chip);
    color: var(--text);
    border-color: var(--line);
  }

  .empty,
  .unknown,
  .new {
    color: var(--muted);
    border: 1px dashed var(--muted);
  }
</style>
