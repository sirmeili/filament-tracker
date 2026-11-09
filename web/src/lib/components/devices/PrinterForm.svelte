<script lang="ts">
  import type { PrinterCheck, PrinterFields } from "#lib/api/admin.ts";
  import { describeError } from "#lib/api/errors.ts";
  import type { PrinterOut } from "#lib/api/types.ts";
  import {
    draftOf,
    printerChanges,
    printerFields,
    printerProblem,
    testResultText,
  } from "#lib/printers.ts";

  /** Add a printer, or edit one (`printer` given). The access code is write-only: its box
   * starts empty, and leaving it empty when editing keeps the saved code. */
  interface Props {
    printer?: PrinterOut;
    onsave: (fields: PrinterFields | Partial<PrinterFields>) => Promise<void>;
    /** Only for a saved printer: try the entered values without saving. */
    ontest?: (values: Partial<PrinterFields>) => Promise<PrinterCheck>;
    oncancel: () => void;
  }

  let { printer, onsave, ontest, oncancel }: Props = $props();

  // The form starts from the printer as it was when the form opened.
  // svelte-ignore state_referenced_locally
  let draft = $state(draftOf(printer));
  let problem = $state<string | null>(null);
  let tested = $state<PrinterCheck | null>(null);
  let busy = $state(false);

  const isNew = $derived(printer === undefined);
  const idBase = $derived(printer ? `printer-${printer.id}` : "printer-new");
  const codePlaceholder = $derived(
    printer?.access_code_set && !printer.access_code_unreadable
      ? "Saved. Leave empty to keep it."
      : "From the printer's screen",
  );

  async function save(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    tested = null;
    problem = printerProblem(draft, isNew);
    if (problem) return;
    busy = true;
    try {
      await onsave(printer ? printerChanges(printer, draft) : printerFields(draft));
    } catch (error) {
      problem = describeError(error);
    } finally {
      busy = false;
    }
  }

  async function test(): Promise<void> {
    if (!ontest || !printer) return;
    tested = null;
    problem = printerProblem(draft, false);
    if (problem) return;
    const { host, port, access_code } = printerChanges(printer, draft);
    busy = true;
    try {
      tested = await ontest({ host, port, access_code });
    } catch (error) {
      problem = describeError(error);
    } finally {
      busy = false;
    }
  }
</script>

<form onsubmit={save} novalidate aria-label={printer ? `Edit ${printer.name}` : "Add a printer"}>
  <div class="row">
    <label class="field">
      Name
      <input type="text" maxlength="100" placeholder="P1S" bind:value={draft.name} />
    </label>
    <label class="field">
      Serial
      <input
        type="text"
        maxlength="32"
        class="mono"
        autocapitalize="characters"
        spellcheck="false"
        bind:value={draft.serial}
      />
    </label>
  </div>
  <div class="row">
    <label class="field wide">
      Address
      <input
        type="text"
        maxlength="255"
        class="mono"
        placeholder="192.168.1.40"
        autocapitalize="none"
        spellcheck="false"
        bind:value={draft.host}
      />
    </label>
    <label class="field narrow">
      Port
      <input type="text" inputmode="numeric" maxlength="5" class="mono" bind:value={draft.port} />
    </label>
  </div>
  <label class="field">
    Access code
    <input
      id="{idBase}-code"
      type="password"
      maxlength="64"
      autocomplete="new-password"
      placeholder={codePlaceholder}
      bind:value={draft.access_code}
    />
  </label>
  <p class="muted small">
    The serial and access code are on the printer's screen, under the LAN settings. For an MQTT
    proxy, use its address and port, and the alias it uses as the serial.
  </p>
  {#if problem}<p role="alert" class="error">{problem}</p>{/if}
  {#if tested}
    <p role="status" class="result" class:ok={tested === "ok"}>{testResultText(tested)}</p>
  {/if}
  <div class="actions">
    <button type="submit" class="primary" disabled={busy}>{isNew ? "Add printer" : "Save"}</button>
    {#if ontest && printer}<button type="button" disabled={busy} onclick={test}>Test</button>{/if}
    <button type="button" disabled={busy} onclick={oncancel}>Cancel</button>
  </div>
</form>

<style>
  form {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .row {
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 6px;
    flex: 1 1 180px;
    font-size: 13px;
    font-weight: 600;
    color: var(--muted);
  }

  .field.wide {
    flex: 3 1 200px;
  }

  .field.narrow {
    flex: 1 1 80px;
  }

  .field input {
    color: var(--text);
  }

  p {
    margin: 0;
  }

  .small {
    font-size: 13px;
  }

  .result {
    padding: 8px 12px;
    border-radius: 10px;
    background: var(--lowbg);
    color: var(--lowtext);
    font-size: 14px;
  }

  .result.ok {
    background: var(--okbg);
    color: var(--oktext);
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }
</style>
