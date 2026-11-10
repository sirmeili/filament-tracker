<script lang="ts">
  import ActionKeys from "#lib/components/phone/ActionKeys.svelte";
  import CountdownBar from "#lib/components/phone/CountdownBar.svelte";
  import DeliveryList from "#lib/components/phone/DeliveryList.svelte";
  import DeliveryPanel from "#lib/components/phone/DeliveryPanel.svelte";
  import DeliveryToggle from "#lib/components/phone/DeliveryToggle.svelte";
  import LastScanBar from "#lib/components/phone/LastScanBar.svelte";
  import ScanCard from "#lib/components/phone/ScanCard.svelte";
  import ScanHeader from "#lib/components/phone/ScanHeader.svelte";
  import ScanResult from "#lib/components/phone/ScanResult.svelte";
  import TapTarget from "#lib/components/phone/TapTarget.svelte";
  import { bridge, type NfcStatus } from "#lib/phone/bridge.ts";
  import { NFC_MESSAGES } from "#lib/phone/card-text.ts";
  import { phone } from "#lib/phone/phone-state.svelte.ts";
  import { pause } from "#lib/phone/pause.ts";
  import type { FlowView } from "#lib/phone/scan-flow.ts";
  import { theme } from "#lib/theme.svelte.ts";

  /** How often to check NFC again while it is off. */
  const NFC_RECHECK_MS = 2000;

  let nfc = $state<NfcStatus | null>(null);
  let view = $state<FlowView | null>(null);

  // Listen for one tag at a time: after a read, wait until the spool has been dealt with
  // (an action chosen, Done, or the timeout) before listening again, so a spool left on the
  // phone is not read over and over. While NFC is off, check again every few seconds, and
  // whenever the app comes back to the front, so turning NFC on needs no restart.
  $effect(() => {
    const session = phone.session;
    if (!session) return;
    const stop = new AbortController();
    let attempt = new AbortController();
    const unsubscribe = session.flow.subscribe((next) => (view = next));
    const onVisible = () => {
      if (document.visibilityState === "visible") attempt.abort();
    };
    document.addEventListener("visibilitychange", onVisible);

    async function listen(): Promise<void> {
      while (!stop.signal.aborted) {
        attempt = new AbortController();
        const signal = AbortSignal.any([stop.signal, attempt.signal]);
        nfc = await bridge().nfcStatus();
        if (nfc !== "ready") {
          await pause(NFC_RECHECK_MS, signal);
          continue;
        }
        try {
          const read = await bridge().readTag(session!.salt, signal);
          if (stop.signal.aborted) return;
          await session!.flow.tapped(read);
          await session!.flow.whenIdle(stop.signal);
        } catch {
          // A tag pulled away mid-read, or the app came back to the front: listen again.
        }
      }
    }

    void listen();
    return () => {
      stop.abort();
      unsubscribe();
      document.removeEventListener("visibilitychange", onVisible);
    };
  });

  const flow = $derived(phone.session?.flow ?? null);
  const appTheme = theme();
  const delivery = phone.delivery;
</script>

<svelte:head><title>Scan · RollCall</title></svelte:head>

<section class="scan" aria-labelledby="scan-h">
  <ScanHeader reach={phone.reach} queueSize={phone.queueSize} theme={appTheme} />

  {#if !phone.app}
    <div class="middle">
      <p class="muted">Scanning works in the RollCall Android app.</p>
    </div>
  {:else if nfc && nfc !== "ready"}
    <div class="middle"><p class="message warn" role="alert">{NFC_MESSAGES[nfc]}</p></div>
  {:else if view && flow && delivery.on}
    <DeliveryList
      rows={delivery.rows}
      totals={delivery.totals}
      undoable={view.phase !== "result" && view.last && !view.last.undone
        ? view.last.eventId
        : null}
      fresh={view.phase === "result" ? (view.last?.eventId ?? null) : null}
      onundo={() => void flow.undoLast()}
      onclear={() => delivery.clear()}
    />
    <DeliveryPanel
      {view}
      onchoose={(action) => void flow.choose(action)}
      onundo={() => void flow.undoLast()}
      onnext={() => flow.dismiss()}
      ontoggle={() => delivery.toggle()}
    />
  {:else if view && flow}
    {#if view.phase === "idle" || view.phase === "looking_up"}
      <TapTarget busy={view.phase === "looking_up"} />
      <div class="bottom">
        {#if view.message}<p class="message {view.tone}" role="status">{view.message}</p>{/if}
        <div class="idle-row">
          {#if view.phase === "idle"}
            <DeliveryToggle on={false} ontoggle={() => delivery.toggle()} />
          {/if}
          {#if view.last}
            <LastScanBar last={view.last} onundo={() => void flow.undoLast()} />
          {/if}
        </div>
      </div>
    {:else if view.phase === "choosing" || view.phase === "sending"}
      <div class="middle">
        {#if view.card}<ScanCard card={view.card} />{/if}
        {#if view.message}<p class="message {view.tone}" role="status">{view.message}</p>{/if}
      </div>
      <div class="bottom">
        {#if view.phase === "sending"}
          <p class="muted sending" role="status">Sending…</p>
        {:else if view.countdown}
          <CountdownBar countdown={view.countdown} label="Pick within 15 s" />
        {/if}
        <ActionKeys
          actions={view.actions}
          suggested={view.suggested}
          busy={view.phase === "sending"}
          onchoose={(action) => void flow.choose(action)}
        />
      </div>
    {:else}
      <ScanResult {view} onundo={() => void flow.undoLast()} onnext={() => flow.dismiss()} />
    {/if}
  {:else}
    <div class="middle"><p class="muted">Starting…</p></div>
  {/if}
</section>

<style>
  .scan {
    display: flex;
    flex-direction: column;
    min-height: 100dvh;
    max-width: 560px;
    margin: 0 auto;
  }

  .scan :global(.middle) {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 20px;
    padding: 0 24px;
    text-align: center;
  }

  .scan :global(.bottom) {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 12px 20px 28px;
  }

  .scan :global(.bottom > button),
  .scan :global(.bottom > .pair > *) {
    min-height: 52px;
    border-radius: 14px;
    font-size: 16px;
  }

  .scan :global(.message) {
    margin: 0;
    padding: 12px 14px;
    border-radius: 12px;
    background: var(--chip);
    text-align: left;
  }

  .scan :global(.message.warn),
  .scan :global(.message.error) {
    background: var(--lowbg);
    color: var(--lowtext);
  }

  .idle-row {
    display: flex;
    align-items: stretch;
    gap: 10px;
  }

  .sending {
    margin: 0;
    font-size: 14px;
    text-align: center;
  }
</style>
