<script lang="ts">
  /** A new device token, shown once with a Copy button and a QR code for the phone app. */
  import QrCode from "#lib/components/devices/QrCode.svelte";
  import { pairingPayload, serverUrlError } from "#lib/pairing.ts";

  interface Props {
    name: string;
    deviceId: string;
    token: string;
    /** The address the admin is using; the default server address for the phone. */
    origin: string;
    ondone: () => void;
  }

  let { name, deviceId, token, origin, ondone }: Props = $props();
  let copied = $state<string | null>(null);
  // svelte-ignore state_referenced_locally
  let serverUrl = $state(origin);
  let urlError = $state<string | null>(null);
  let payload = $state<string | null>(null);

  function showQr(event: SubmitEvent): void {
    event.preventDefault();
    urlError = serverUrlError(serverUrl);
    payload = urlError ? null : pairingPayload(serverUrl, token, deviceId);
  }

  async function copy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(token);
      copied = "Copied.";
    } catch {
      copied = "Could not copy. Select the token and copy it by hand.";
    }
  }
</script>

<section class="panel" role="alert" aria-label="New token for {name}">
  <strong>Copy the token for {name} now. It won't be shown again.</strong>
  <div class="row">
    <code>{token}</code>
    <button type="button" onclick={copy}>Copy</button>
    <button type="button" class="primary" onclick={ondone}>Done</button>
  </div>
  {#if copied}<span>{copied}</span>{/if}
  <span class="muted">
    Enter it in the scanner's setup screen, or pair the phone app below. Scanner routes accept it
    only from your LAN.
  </span>
  {#if payload}
    <div class="pair">
      <QrCode text={payload} label="Pairing QR code for {name}" />
      <span class="muted">
        In the Filament Tracker app, choose Pair and scan this code. It holds the token, so don't
        share it.
      </span>
    </div>
  {:else}
    <form class="row" novalidate onsubmit={showQr}>
      <label
        >Server address for the phone<input
          type="url"
          bind:value={serverUrl}
          aria-invalid={urlError ? "true" : undefined}
        /></label
      >
      <button type="submit">Show QR code</button>
    </form>
    {#if urlError}<span role="status">{urlError}</span>{/if}
  {/if}
</section>

<style>
  .panel {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 16px 20px;
    border-radius: 16px;
    background: var(--lowbg);
    color: var(--lowtext);
  }

  .row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
  }

  code {
    flex: 1 1 280px;
    font-family: var(--font-mono);
    font-size: 14px;
    padding: 10px 12px;
    border-radius: 10px;
    background: var(--surface);
    color: var(--text);
    word-break: break-all;
    user-select: all;
  }

  label {
    display: flex;
    flex: 1 1 280px;
    flex-direction: column;
    gap: 4px;
    font-size: 13px;
  }

  .pair {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 16px;
  }

  .muted {
    color: inherit;
    font-size: 13px;
  }
</style>
