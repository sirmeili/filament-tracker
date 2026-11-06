<script lang="ts">
  import ActionKeys from "#lib/components/phone/ActionKeys.svelte";
  import ScanCard from "#lib/components/phone/ScanCard.svelte";
  import { bridge, type NfcStatus } from "#lib/phone/bridge.ts";
  import { NFC_MESSAGES } from "#lib/phone/card-text.ts";
  import { phone } from "#lib/phone/phone-state.svelte.ts";
  import type { FlowView } from "#lib/phone/scan-flow.ts";

  let nfc = $state<NfcStatus | null>(null);
  let view = $state<FlowView | null>(null);

  // Keep the phone listening for tags while this screen is open.
  $effect(() => {
    const session = phone.session;
    if (!session) return;
    const stop = new AbortController();
    const unsubscribe = session.flow.subscribe((next) => (view = next));

    async function listen(): Promise<void> {
      nfc = await bridge().nfcStatus();
      while (nfc === "ready" && !stop.signal.aborted) {
        try {
          const read = await bridge().readTag(session!.salt, stop.signal);
          if (!stop.signal.aborted) await session!.flow.tapped(read);
        } catch {
          if (stop.signal.aborted) return;
          // A tag pulled away mid-read: keep listening for the next tap.
          nfc = await bridge().nfcStatus();
        }
      }
    }

    void listen();
    return () => {
      stop.abort();
      unsubscribe();
    };
  });

  const flow = $derived(phone.session?.flow ?? null);
</script>

<svelte:head><title>Scan · Filament Tracker</title></svelte:head>

<section class="scan" aria-labelledby="scan-h">
  <div class="head">
    <h1 id="scan-h">Scan</h1>
    {#if phone.queueSize > 0}
      <span class="queue" role="status">{phone.queueSize} queued</span>
    {/if}
  </div>

  {#if !phone.app}
    <p class="muted">Scanning works in the Filament Tracker Android app.</p>
  {:else if nfc && nfc !== "ready"}
    <p class="warn" role="alert">{NFC_MESSAGES[nfc]}</p>
  {:else if view && flow}
    {#if view.phase === "idle"}
      <p class="prompt">Tap a spool on the back of the phone.</p>
    {:else if view.phase === "looking_up"}
      <p class="prompt" role="status">Looking it up…</p>
    {/if}

    {#if view.card && view.phase !== "idle"}
      <ScanCard card={view.card} />
    {/if}

    {#if view.message}
      <p class="message {view.tone}" role="status">{view.message}</p>
    {/if}

    {#if view.phase === "choosing" || view.phase === "sending"}
      <ActionKeys
        actions={view.actions}
        suggested={view.suggested}
        busy={view.phase === "sending"}
        onchoose={(action) => void flow.choose(action)}
      />
    {:else if view.phase === "result"}
      <button type="button" onclick={() => flow.dismiss()}>Done</button>
    {/if}

    {#if view.last && view.phase !== "choosing"}
      <div class="last">
        <span class="muted"
          >Last scan: {view.last.card.name}{view.last.undone ? " (undone)" : ""}</span
        >
        {#if !view.last.undone}
          <button type="button" onclick={() => void flow.undoLast()}>Undo</button>
        {/if}
      </div>
    {/if}
  {:else}
    <p class="muted">Starting…</p>
  {/if}

  <p class="links">
    <a href="/">Open the full app</a> · <a href="/pair">Pairing</a>
  </p>
</section>

<style>
  .scan {
    display: flex;
    flex-direction: column;
    gap: 16px;
    max-width: 560px;
    margin: 0 auto;
  }

  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  h1 {
    margin: 0;
  }

  .queue {
    font-size: 13px;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 999px;
    background: var(--lowbg);
    color: var(--lowtext);
  }

  .prompt {
    font-size: 20px;
    text-align: center;
    padding: 32px 0;
    margin: 0;
  }

  .message,
  .warn {
    margin: 0;
    padding: 12px 14px;
    border-radius: 12px;
    background: var(--chip);
  }

  .message.warn,
  .warn,
  .message.error {
    background: var(--lowbg);
    color: var(--lowtext);
  }

  .last {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .links {
    text-align: center;
    font-size: 14px;
  }
</style>
