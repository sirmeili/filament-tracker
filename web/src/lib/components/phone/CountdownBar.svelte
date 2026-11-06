<script lang="ts">
  import type { Countdown } from "#lib/phone/scan-flow.ts";

  /** A bar that empties over the flow's running timer. Each new timer (a new id) starts a
   * new bar, so it always matches the timer that will act. */
  interface Props {
    countdown: Countdown;
    label: string;
  }

  let { countdown, label }: Props = $props();
</script>

<div class="countdown">
  <span>{label}</span>
  <div class="track" aria-hidden="true">
    {#key countdown.id}
      <div class="fill" data-ms={countdown.ms} style:animation-duration="{countdown.ms}ms"></div>
    {/key}
  </div>
</div>

<style>
  .countdown {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 13px;
    color: var(--muted);
  }

  .track {
    flex: 1;
    height: 4px;
    border-radius: 999px;
    background: var(--track);
    overflow: hidden;
  }

  .fill {
    height: 100%;
    width: 0;
    background: var(--muted);
    border-radius: 999px;
    animation-name: drain;
    animation-timing-function: linear;
    animation-fill-mode: forwards;
  }

  @keyframes drain {
    from {
      width: 100%;
    }
    to {
      width: 0;
    }
  }
</style>
