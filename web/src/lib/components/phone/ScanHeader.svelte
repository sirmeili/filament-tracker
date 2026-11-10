<script lang="ts">
  import type { Reach } from "#lib/phone/device-api.ts";

  interface Props {
    /** How the last request reached the server; null until known. */
    reach: Reach | null;
    queueSize: number;
  }

  let { reach, queueSize }: Props = $props();

  const NAMES: Record<Reach, string> = { online: "Online", offline: "Offline", away: "Away" };

  const label = $derived.by(() => {
    const queued = queueSize > 0 ? ` · ${queueSize} queued` : "";
    if (reach === null) return queueSize > 0 ? `${queueSize} queued` : null;
    return NAMES[reach] + queued;
  });
  const hint = $derived(
    reach === "away" ? "Away from home: scans are sent when you're back." : undefined,
  );
</script>

<div class="head">
  <h1 id="scan-h">Scan</h1>
  {#if label}
    <span
      class="pill"
      class:off={(reach !== null && reach !== "online") || queueSize > 0}
      role="status"
      title={hint}
    >
      <span class="dot" aria-hidden="true"></span>{label}
    </span>
  {/if}
  <a class="icon" href="/pair" aria-label="Phone pairing" title="Phone pairing">
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      aria-hidden="true"
    >
      <path d="M10 14a5 5 0 0 0 7.07 0l3-3a5 5 0 0 0-7.07-7.07l-1 1"></path>
      <path d="M14 10a5 5 0 0 0-7.07 0l-3 3a5 5 0 0 0 7.07 7.07l1-1"></path>
    </svg>
  </a>
  <a class="icon" href="/" aria-label="Open the full app" title="Open the full app">
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      aria-hidden="true"
    >
      <rect x="3" y="3" width="7" height="7" rx="1.5"></rect>
      <rect x="14" y="3" width="7" height="7" rx="1.5"></rect>
      <rect x="3" y="14" width="7" height="7" rx="1.5"></rect>
      <rect x="14" y="14" width="7" height="7" rx="1.5"></rect>
    </svg>
  </a>
</div>

<style>
  .head {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 18px 16px 10px 20px;
  }

  h1 {
    margin: 0;
    flex: 1;
    font-size: 28px;
    letter-spacing: -0.01em;
  }

  .pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    font-weight: 600;
    padding: 5px 10px;
    border-radius: 999px;
    background: var(--okbg);
    color: var(--oktext);
    white-space: nowrap;
  }

  .pill.off {
    background: var(--lowbg);
    color: var(--lowtext);
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: currentColor;
  }

  .icon {
    width: 44px;
    height: 44px;
    flex: none;
    box-sizing: border-box;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 12px;
    border: 1px solid var(--line);
    background: var(--surface);
    color: var(--text);
  }
</style>
