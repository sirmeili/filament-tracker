<script lang="ts">
  import type { DeviceOut } from "#lib/api/types.ts";
  import { deviceStatus, seenText, STATUS_LABELS } from "#lib/devices.ts";

  interface Props {
    device: DeviceOut;
    busy: boolean;
    onrotate: (device: DeviceOut) => void;
    onrevoke: (device: DeviceOut) => void;
  }

  let { device, busy, onrotate, onrevoke }: Props = $props();

  /** Which action is waiting for a second click to confirm. */
  let confirming = $state<"rotate" | "revoke" | null>(null);
  const status = $derived(deviceStatus(device));

  function confirm(): void {
    if (confirming === "rotate") onrotate(device);
    else onrevoke(device);
    confirming = null;
  }
</script>

<article aria-label={device.name}>
  <div class="head">
    <div class="name">
      <h3>{device.name}</h3>
      <div class="muted small"><span class="mono">{device.id}</span> · {seenText(device)}</div>
    </div>
    <span class="status {status}"
      ><span class="dot" aria-hidden="true"></span>{STATUS_LABELS[status]}</span
    >
  </div>
  <dl>
    <div>
      <dt>Belongs to</dt>
      <dd>{device.owner ?? "Shared"}</dd>
    </div>
    <div>
      <dt>Firmware</dt>
      <dd>{device.fw_version ?? "—"}</dd>
    </div>
    <div>
      <dt>Queued</dt>
      <dd>{device.queue_length ?? "—"}</dd>
    </div>
  </dl>
  {#if confirming}
    <div class="actions" role="group" aria-label="Confirm">
      <span class="small">
        {confirming === "rotate"
          ? "The old token stops working at once."
          : "The scanner can no longer send scans."}
      </span>
      <button type="button" class="primary" disabled={busy} onclick={confirm}>
        {confirming === "rotate" ? "Rotate token" : "Revoke"}
      </button>
      <button type="button" onclick={() => (confirming = null)}>Cancel</button>
    </div>
  {:else}
    <div class="actions">
      <button type="button" disabled={busy} onclick={() => (confirming = "rotate")}>
        {device.revoked ? "New token (re-enable)" : "Rotate token"}
      </button>
      {#if !device.revoked}
        <button type="button" class="danger" disabled={busy} onclick={() => (confirming = "revoke")}
          >Revoke</button
        >
      {/if}
    </div>
  {/if}
</article>

<style>
  article {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .head {
    display: flex;
    align-items: flex-start;
    gap: 12px;
  }

  .name {
    flex: 1;
    min-width: 0;
  }

  h3 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
  }

  .small {
    font-size: 13px;
  }

  .status {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 999px;
    background: var(--chip);
    color: var(--muted);
    white-space: nowrap;
  }

  .status.online {
    background: var(--okbg);
    color: var(--oktext);
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: currentColor;
  }

  .status.online .dot {
    background: var(--okdot);
  }

  dl {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
    margin: 0;
  }

  dt {
    font-size: 12px;
    color: var(--muted);
  }

  dd {
    margin: 2px 0 0;
    font-family: var(--font-mono);
    font-weight: 500;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }
</style>
