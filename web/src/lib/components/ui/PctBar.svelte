<script lang="ts">
  /** An open spool's remaining % from the AMS, or a note when the AMS has not reported. */
  interface Props {
    pct: number | null;
    low?: boolean;
    /** Shown instead of a bar when `pct` is null. */
    unknownText?: string;
  }

  let { pct, low = false, unknownText = "Not seen by the AMS" }: Props = $props();
</script>

{#if pct === null}
  <span class="unknown">{unknownText}</span>
{:else}
  <span class="row">
    <span class="bar" class:low aria-hidden="true">
      <span style:width="{Math.max(0, Math.min(100, pct))}%"></span>
    </span>
    <span class="pct" class:low>{pct}%</span>
  </span>
{/if}

<style>
  .row {
    display: flex;
    align-items: center;
    gap: 10px;
    flex: 1;
  }

  .bar {
    flex: 1;
    height: 8px;
    min-width: 40px;
    border-radius: 999px;
    background: var(--track);
    overflow: hidden;
  }

  .bar > span {
    display: block;
    height: 100%;
    border-radius: 999px;
    background: var(--fill);
  }

  .bar.low > span {
    background: var(--fillLow);
  }

  .pct {
    font-family: var(--font-mono);
    font-size: 13px;
    font-weight: 700;
    width: 40px;
    text-align: right;
  }

  .pct.low {
    color: var(--lowtext);
  }

  .unknown {
    font-size: 13px;
    color: var(--muted);
  }
</style>
