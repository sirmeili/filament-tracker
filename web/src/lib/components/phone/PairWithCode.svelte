<script lang="ts">
  // Pairing with a code from the Devices page (Pairing in docs/SPEC.md): for a shared phone
  // that belongs to no one. Scan the QR code, or type the details.
  import { goto } from "$app/navigation";
  import { checkPairing, parsePairing, type PairingFields } from "#lib/pairing.ts";
  import { bridge } from "#lib/phone/bridge.ts";
  import { pairingError, phone } from "#lib/phone/phone-state.svelte.ts";

  let busy = $state(false);
  let error = $state<string | null>(null);
  let typing = $state(false);
  let url = $state("");
  let deviceId = $state("");
  let token = $state("");

  async function pairWith(fields: PairingFields): Promise<void> {
    busy = true;
    error = null;
    try {
      await phone.pair(fields);
      await goto("/scan");
    } catch (failure) {
      error = pairingError(failure);
    } finally {
      busy = false;
    }
  }

  async function scanCode(): Promise<void> {
    error = null;
    let text: string | null;
    try {
      text = await bridge().scanQr();
    } catch {
      error = "The camera could not be opened. Type the details instead.";
      return;
    }
    if (text === null) return;
    const parsed = parsePairing(text);
    if ("error" in parsed) error = parsed.error;
    else await pairWith(parsed.pairing);
  }

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    const checked = checkPairing(url, token, deviceId);
    if ("error" in checked) error = checked.error;
    else await pairWith(checked.pairing);
  }
</script>

<p>
  On the Devices page of the web app, an Admin registers this phone as a scanner and chooses Show QR
  code. Then scan that code here.
</p>
<button type="button" class="primary" disabled={busy} onclick={scanCode}>Scan pairing code</button>

{#if typing}
  <form novalidate onsubmit={submit}>
    <label>Server address<input type="url" bind:value={url} autocomplete="off" /></label>
    <label>Device ID<input type="text" bind:value={deviceId} autocomplete="off" /></label>
    <label>Token<input type="password" bind:value={token} autocomplete="off" /></label>
    <button type="submit" disabled={busy}>Pair</button>
  </form>
{:else}
  <button type="button" onclick={() => (typing = true)}>Type the details instead</button>
{/if}

{#if busy}<p class="muted" role="status">Checking with the server…</p>{/if}
{#if error}<p class="warn" role="alert">{error}</p>{/if}

<style>
  p {
    margin: 0;
  }

  form {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  label {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .warn {
    padding: 12px 14px;
    border-radius: 12px;
    background: var(--lowbg);
    color: var(--lowtext);
  }
</style>
