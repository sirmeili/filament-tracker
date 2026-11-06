<script lang="ts">
  import { MIN_PASSWORD, passwordMeterText, passwordProgress } from "#lib/password.ts";

  /** Progress toward the minimum password length. */
  let { password }: { password: string } = $props();
  const progress = $derived(passwordProgress(password));
</script>

<div class="meter">
  <div
    class="track"
    role="meter"
    aria-label="Password length"
    aria-valuemin={0}
    aria-valuemax={MIN_PASSWORD}
    aria-valuenow={Math.min(password.length, MIN_PASSWORD)}
  >
    <span class:done={progress === 1} style:width="{progress * 100}%"></span>
  </div>
  <span class="text">{passwordMeterText(password)}</span>
</div>

<style>
  .meter {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 13px;
    color: var(--muted);
  }

  .track {
    flex: 1;
    height: 8px;
    border-radius: 999px;
    background: var(--track);
    overflow: hidden;
  }

  .track span {
    display: block;
    height: 100%;
    border-radius: 999px;
    background: var(--fillLow);
  }

  .track span.done {
    background: var(--okdot);
  }

  .text {
    min-width: 150px;
  }
</style>
