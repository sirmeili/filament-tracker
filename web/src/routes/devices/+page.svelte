<script lang="ts">
  import {
    listDevices,
    listPrinters,
    registerDevice,
    revokeDevice,
    rotateToken,
    unpinPrinter,
  } from "#lib/api/admin.ts";
  import { describeError } from "#lib/api/errors.ts";
  import type { DeviceOut, PrinterOut } from "#lib/api/types.ts";
  import DeviceCard from "#lib/components/devices/DeviceCard.svelte";
  import PrinterCard from "#lib/components/devices/PrinterCard.svelte";
  import TokenPanel from "#lib/components/devices/TokenPanel.svelte";
  import { DEVICE_ID_PATTERN, deviceId } from "#lib/devices.ts";

  let devices = $state<DeviceOut[] | null>(null);
  let failure = $state<string | null>(null);
  let printers = $state<PrinterOut[] | null>(null);
  let printerFailure = $state<string | null>(null);
  let message = $state<string | null>(null);
  let busy = $state(false);

  let registering = $state(false);
  let name = $state("");
  let id = $state("");
  let idEdited = $state(false);
  let formProblem = $state<string | null>(null);
  /** A token to show once: after registering or rotating. */
  let shown = $state<{ name: string; token: string } | null>(null);

  async function load(): Promise<void> {
    try {
      devices = await listDevices();
      failure = null;
    } catch (error) {
      failure = describeError(error);
    }
  }

  async function loadPrinters(): Promise<void> {
    try {
      printers = await listPrinters();
      printerFailure = null;
    } catch (error) {
      printerFailure = describeError(error);
    }
  }

  $effect(() => {
    void load();
    void loadPrinters();
  });

  function typedName(value: string): void {
    name = value;
    if (!idEdited) id = deviceId(value);
  }

  function closeForm(): void {
    registering = false;
    name = "";
    id = "";
    idEdited = false;
    formProblem = null;
  }

  async function register(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (!name.trim()) return void (formProblem = "Enter a name.");
    if (!DEVICE_ID_PATTERN.test(id)) {
      return void (formProblem =
        "IDs use lower-case letters, digits and '-', starting with a letter or digit.");
    }
    busy = true;
    try {
      const created = await registerDevice(id, name.trim());
      shown = { name: created.name, token: created.token };
      closeForm();
      await load();
    } catch (error) {
      formProblem = describeError(error);
    } finally {
      busy = false;
    }
  }

  async function change(run: () => Promise<void>): Promise<void> {
    busy = true;
    message = null;
    try {
      await run();
      await load();
    } catch (error) {
      message = describeError(error);
    } finally {
      busy = false;
    }
  }

  function rotate(device: DeviceOut): Promise<void> {
    return change(async () => {
      const created = await rotateToken(device.id);
      shown = { name: created.name, token: created.token };
    });
  }

  function unpin(printer: PrinterOut): Promise<void> {
    return change(async () => {
      await unpinPrinter(printer.id);
      message = `Forgot the certificate pin for ${printer.name}. The next connection pins a new one.`;
      await loadPrinters();
    });
  }

  function revoke(device: DeviceOut): Promise<void> {
    return change(async () => {
      await revokeDevice(device.id);
      message = `Revoked ${device.name}.`;
    });
  }
</script>

<svelte:head><title>Devices · Filament Tracker</title></svelte:head>

<div class="page">
  <div class="pagehead">
    <div>
      <h1>Devices</h1>
      <p>Scanners and printers that report to this server. Admins only.</p>
    </div>
    {#if !registering}
      <button type="button" class="primary" onclick={() => (registering = true)}
        >Register scanner</button
      >
    {/if}
  </div>

  {#if registering}
    <form class="card" onsubmit={register} aria-labelledby="reg-h" novalidate>
      <h2 id="reg-h" class="label">Register a scanner</h2>
      <div class="row">
        <label class="field">
          Name
          <input
            type="text"
            maxlength="100"
            placeholder="Office scanner"
            value={name}
            oninput={(e) => typedName(e.currentTarget.value)}
          />
        </label>
        <label class="field">
          ID
          <input
            type="text"
            maxlength="64"
            class="mono"
            value={id}
            oninput={(e) => {
              id = e.currentTarget.value;
              idEdited = true;
            }}
          />
        </label>
      </div>
      {#if formProblem}<p role="alert" class="error">{formProblem}</p>{/if}
      <div class="actions">
        <button type="submit" class="primary" disabled={busy}>Create token</button>
        <button type="button" onclick={closeForm}>Cancel</button>
      </div>
    </form>
  {/if}

  {#if shown}
    <TokenPanel
      name={shown.name}
      token={shown.token}
      origin={window.location.origin}
      ondone={() => (shown = null)}
    />
  {/if}
  {#if message}<p role="status" class="muted">{message}</p>{/if}

  <section aria-labelledby="sc-h">
    <h2 id="sc-h">Scanners</h2>
    {#if failure}
      <p role="alert" class="error">{failure}</p>
    {:else if !devices}
      <p class="muted">Loading…</p>
    {:else if devices.length === 0}
      <p class="muted">No scanners yet. Register one to get its token.</p>
    {:else}
      <div class="grid">
        {#each devices as device (device.id)}
          <DeviceCard {device} {busy} onrotate={rotate} onrevoke={revoke} />
        {/each}
      </div>
    {/if}
  </section>

  <section aria-labelledby="pr-h">
    <h2 id="pr-h">Printers</h2>
    {#if printerFailure}
      <p role="alert" class="error">{printerFailure}</p>
    {:else if !printers}
      <p class="muted">Loading…</p>
    {:else if printers.length === 0}
      <p class="muted">
        No printers yet. Add them with the <span class="mono">PRINTERS</span> setting on the server.
      </p>
    {:else}
      <div class="grid">
        {#each printers as printer (printer.id)}
          <PrinterCard {printer} {busy} onunpin={unpin} />
        {/each}
      </div>
    {/if}
  </section>
</div>

<style>
  section {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  h2:not(.label) {
    margin: 0;
    font-size: 22px;
    font-weight: 600;
  }

  section p {
    margin: 0;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 16px;
  }

  form {
    max-width: 720px;
  }

  .row {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 6px;
    flex: 1 1 220px;
    font-size: 13px;
    font-weight: 600;
    color: var(--muted);
  }

  .field input {
    color: var(--text);
  }

  .actions {
    display: flex;
    gap: 10px;
  }
</style>
