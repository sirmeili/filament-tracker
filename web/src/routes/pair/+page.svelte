<script lang="ts">
  import { goto } from "$app/navigation";
  import { checkPairing, parsePairing, type PairingFields } from "#lib/pairing.ts";
  import { bridge } from "#lib/phone/bridge.ts";
  import { pairingError, phone } from "#lib/phone/phone-state.svelte.ts";

  let busy = $state(false);
  let error = $state<string | null>(null);
  let typing = $state(false);
  let confirmingForget = $state(false);
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

  async function forget(): Promise<void> {
    confirmingForget = false;
    await phone.unpair();
  }
</script>

<svelte:head><title>Pairing · Filament Tracker</title></svelte:head>

<section class="pair" aria-labelledby="pair-h">
  <h1 id="pair-h">Pairing</h1>

  {#if !phone.app}
    <p class="muted">Pairing is for the Filament Tracker Android app.</p>
  {:else if phone.session}
    <p>
      Paired with <span class="mono">{phone.session.pairing.url}</span> as
      <span class="mono">{phone.session.pairing.deviceId}</span>.
    </p>
    {#if phone.queueSize > 0}
      <p class="warn" role="alert">
        {phone.queueSize} queued scans have not been sent yet. Forgetting the pairing drops them.
      </p>
    {/if}
    {#if confirmingForget}
      <div class="row" role="group" aria-label="Confirm">
        <button type="button" class="primary" onclick={forget}>Forget pairing</button>
        <button type="button" onclick={() => (confirmingForget = false)}>Cancel</button>
      </div>
    {:else}
      <div class="row">
        <a class="button primary" href="/scan">Scan</a>
        <button type="button" onclick={() => (confirmingForget = true)}>Forget pairing</button>
      </div>
    {/if}
  {:else}
    <p>
      On the Devices page of the web app, register this phone as a scanner and choose Show QR code.
      Then scan that code here.
    </p>
    <button type="button" class="primary" disabled={busy} onclick={scanCode}
      >Scan pairing code</button
    >

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
  {/if}

  {#if busy}<p class="muted" role="status">Checking with the server…</p>{/if}
  {#if error}<p class="warn" role="alert">{error}</p>{/if}
</section>

<style>
  .pair {
    display: flex;
    flex-direction: column;
    gap: 16px;
    max-width: 560px;
    margin: 0 auto;
  }

  h1 {
    margin: 0;
  }

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

  .row {
    display: flex;
    gap: 10px;
  }

  .warn {
    padding: 12px 14px;
    border-radius: 12px;
    background: var(--lowbg);
    color: var(--lowtext);
  }
</style>
