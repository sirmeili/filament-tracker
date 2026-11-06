<script lang="ts">
  /** A confirmation after a change, with an optional button that reverses it. */
  interface Props {
    message: string;
    actionLabel?: string;
    busy?: boolean;
    onaction?: () => void;
  }

  let { message, actionLabel, busy = false, onaction }: Props = $props();
</script>

<div class="banner" role="status">
  <svg
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2.4"
    aria-hidden="true"
  >
    <path d="M20 6 9 17l-5-5"></path>
  </svg>
  <span class="text">{message}</span>
  {#if actionLabel && onaction}
    <button type="button" class="small" disabled={busy} onclick={onaction}>{actionLabel}</button>
  {/if}
</div>

<style>
  .banner {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    border-radius: 12px;
    background: var(--text);
    color: var(--bg);
  }

  .text {
    flex: 1;
    font-size: 15px;
    font-weight: 500;
  }
</style>
