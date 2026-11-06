<script lang="ts">
  import type { SpoolState } from "#lib/api/types.ts";
  import { STATE_LABELS } from "#lib/format.ts";

  let { state }: { state: SpoolState } = $props();
</script>

<span class="st {state}">{STATE_LABELS[state]}</span>

<style>
  .st {
    display: inline-flex;
    align-items: center;
    font-size: 12px;
    font-weight: 700;
    padding: 3px 9px;
    border-radius: 6px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    white-space: nowrap;
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
  .unknown {
    color: var(--muted);
    border: 1px dashed var(--muted);
  }
</style>
