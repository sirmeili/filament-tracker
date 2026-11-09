<script lang="ts">
  import type { PrinterCheck, PrinterFields } from "#lib/api/admin.ts";
  import type { PrinterOut } from "#lib/api/types.ts";
  import PrinterForm from "#lib/components/devices/PrinterForm.svelte";
  import PctBar from "#lib/components/ui/PctBar.svelte";
  import Ring from "#lib/components/ui/Ring.svelte";
  import {
    accessCodeNote,
    amsName,
    byAms,
    PRINTER_STATUS_LABELS,
    printerStatus,
    reportText,
    shortFingerprint,
    slotName,
  } from "#lib/printers.ts";

  interface Props {
    printer: PrinterOut;
    busy: boolean;
    onunpin: (printer: PrinterOut) => void;
    /** Save changes; rejects with the server's problem to show in the form. */
    onedit: (printer: PrinterOut, changes: Partial<PrinterFields>) => Promise<void>;
    ontest: (printer: PrinterOut, values: Partial<PrinterFields>) => Promise<PrinterCheck>;
    onremove: (printer: PrinterOut) => void;
  }

  let { printer, busy, onunpin, onedit, ontest, onremove }: Props = $props();

  let confirming = $state(false);
  let editing = $state(false);
  let removing = $state(false);
  const status = $derived(printerStatus(printer));
  const units = $derived(byAms(printer.slots));
  const codeNote = $derived(accessCodeNote(printer));

  async function save(changes: Partial<PrinterFields>): Promise<void> {
    await onedit(printer, changes);
    editing = false;
  }
</script>

<article aria-label={printer.name}>
  <div class="head">
    <div class="name">
      <h3>{printer.name}</h3>
      <div class="muted small">
        <span class="mono">{printer.host}:{printer.port}</span> · {reportText(printer)}
      </div>
      <div class="muted small">Serial <span class="mono">{printer.serial}</span></div>
    </div>
    <span class="status {status}"
      ><span class="dot" aria-hidden="true"></span>{PRINTER_STATUS_LABELS[status]}</span
    >
  </div>

  {#if editing}
    <PrinterForm
      {printer}
      onsave={save}
      ontest={(values) => ontest(printer, values)}
      oncancel={() => (editing = false)}
    />
  {/if}

  {#if codeNote}<p class="warn" role="alert">{codeNote}</p>{/if}

  {#if status === "pin_mismatch"}
    <p class="warn" role="alert">
      The printer presented a different certificate{#if printer.presented_sha256}
        (<span class="mono">{shortFingerprint(printer.presented_sha256)}</span>){/if}, so the server
      is not connecting. If its firmware was just updated, forget the pin so the next connection
      pins the new certificate.
    </p>
  {/if}

  {#if units.length === 0}
    <p class="muted small">No AMS reported yet.</p>
  {/if}
  {#each units as unit (unit.ams)}
    <div class="ams">
      <h4 class="label">{amsName(unit.ams)}</h4>
      <ul>
        {#each unit.slots as slot (slot.tray_index)}
          <li aria-label={slotName(slot.ams_index, slot.tray_index)}>
            <span class="slotno mono">{slot.tray_index + 1}</span>
            {#if slot.color_rgba}
              <Ring rgba={slot.color_rgba} size="sm" />
            {:else}
              <span class="empty-ring" aria-hidden="true"></span>
            {/if}
            <span class="what">
              {#if slot.spool}
                <a href="/spools/{slot.spool.id}"
                  >{slot.spool.product.display_name} <span class="mono">#{slot.spool.id}</span></a
                >
              {:else if slot.filament_type}
                <span>{slot.filament_type}</span>
                <span class="muted small">No Bambu tag, not tracked</span>
              {:else}
                <span class="muted">Empty</span>
              {/if}
            </span>
            {#if slot.remaining_pct !== null}
              <span class="pct"
                ><PctBar pct={slot.remaining_pct} low={slot.remaining_pct === 0} /></span
              >
            {/if}
          </li>
        {/each}
      </ul>
    </div>
  {/each}

  <div class="pin small">
    {#if printer.pinned_sha256}
      Certificate pinned · <span class="mono">{shortFingerprint(printer.pinned_sha256)}</span>
    {:else}
      <span class="muted">No certificate pinned yet; the next connection pins one.</span>
    {/if}
  </div>

  {#if removing}
    <div class="actions" role="group" aria-label="Confirm removal">
      <span class="small"
        >The server stops watching {printer.name} and forgets its AMS slots. Its events stay.</span
      >
      <button
        type="button"
        class="primary"
        disabled={busy}
        onclick={() => {
          removing = false;
          onremove(printer);
        }}>Remove</button
      >
      <button type="button" onclick={() => (removing = false)}>Cancel</button>
    </div>
  {:else if !editing}
    <div class="actions">
      <button type="button" disabled={busy} onclick={() => (editing = true)}>Edit</button>
      <button type="button" disabled={busy} onclick={() => (removing = true)}>Remove</button>
    </div>
  {/if}

  {#if printer.pinned_sha256}
    {#if confirming}
      <div class="actions" role="group" aria-label="Confirm">
        <span class="small">The next connection trusts whatever certificate it finds.</span>
        <button
          type="button"
          class="primary"
          disabled={busy}
          onclick={() => {
            confirming = false;
            onunpin(printer);
          }}>Forget pin</button
        >
        <button type="button" onclick={() => (confirming = false)}>Cancel</button>
      </div>
    {:else}
      <div class="actions">
        <button
          type="button"
          class:primary={status === "pin_mismatch"}
          disabled={busy}
          onclick={() => (confirming = true)}>Forget pin</button
        >
      </div>
    {/if}
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

  h4 {
    margin: 0 0 8px;
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

  .status.pin_mismatch {
    background: var(--lowbg);
    color: var(--lowtext);
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

  .warn {
    margin: 0;
    padding: 12px 14px;
    border-radius: 12px;
    background: var(--lowbg);
    color: var(--lowtext);
    font-size: 14px;
  }

  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  li {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 36px;
  }

  .slotno {
    width: 16px;
    color: var(--muted);
    font-size: 13px;
  }

  .empty-ring {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    border: 2px dashed var(--line);
    flex: none;
  }

  .what {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }

  .what a {
    font-weight: 600;
  }

  .pct {
    width: 110px;
    flex: none;
  }

  .pin {
    color: var(--muted);
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }
</style>
