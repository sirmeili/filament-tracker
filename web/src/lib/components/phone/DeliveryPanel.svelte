<script lang="ts">
  import ActionKeys from "#lib/components/phone/ActionKeys.svelte";
  import CountdownBar from "#lib/components/phone/CountdownBar.svelte";
  import DeliveryToggle from "#lib/components/phone/DeliveryToggle.svelte";
  import ScanIcon from "#lib/components/phone/ScanIcon.svelte";
  import Ring from "#lib/components/ui/Ring.svelte";
  import CardChip from "#lib/components/phone/CardChip.svelte";
  import { cardLine } from "#lib/phone/card-text.ts";
  import type { ScreenAction } from "#lib/phone/device-api.ts";
  import { actionName, type FlowView } from "#lib/phone/scan-flow.ts";

  /** The bottom panel while unpacking a delivery: Ready, then the spool with its keys, then
   * what was recorded. The Delivery toggle shows only while waiting, so the mode cannot
   * change halfway through a choice. */
  interface Props {
    view: FlowView;
    onchoose: (action: ScreenAction) => void;
    onundo: () => void;
    onnext: () => void;
    ontoggle: () => void;
  }

  let { view, onchoose, onundo, onnext, ontoggle }: Props = $props();

  const recorded = $derived(
    (view.outcome === "recorded" || view.outcome === "queued") && view.last && !view.last.undone
      ? view.last
      : null,
  );
</script>

<div class="bottom">
  {#if view.phase === "idle" || view.phase === "looking_up"}
    {#if view.message}<p class="message {view.tone}" role="status">{view.message}</p>{/if}
    <div class="ready-row">
      {#if view.phase === "idle"}<DeliveryToggle on={true} {ontoggle} />{/if}
      <div class="ready">
        <span class="target" class:busy={view.phase === "looking_up"} aria-hidden="true">
          <span class="ping"></span>
          <span class="ping b"></span>
          <span class="icon"><ScanIcon size={34} /></span>
        </span>
        <span>
          {#if view.phase === "looking_up"}
            <span class="title" role="status">Looking it up…</span>
          {:else}
            <span class="title">Ready</span>
            <span class="sub muted">Tap the next spool on the back of the phone.</span>
          {/if}
        </span>
      </div>
    </div>
  {:else if view.phase === "choosing" || view.phase === "sending"}
    <section class="panel found" aria-label="Scanned spool">
      <div class="inner">
        {#if view.card}
          <article class="spool" aria-label="Spool">
            <Ring rgba={view.card.colorRgba ?? "00000000"} />
            <div>
              <CardChip card={view.card} />
              <h3>{view.card.name}</h3>
              <p class="muted">{cardLine(view.card)}</p>
            </div>
          </article>
        {/if}
        {#if view.message}<p class="message {view.tone}" role="status">{view.message}</p>{/if}
        <ActionKeys
          actions={view.actions}
          suggested={view.suggested}
          busy={view.phase === "sending"}
          {onchoose}
        />
      </div>
      {#if view.phase === "choosing" && view.countdown}
        <CountdownBar countdown={view.countdown} />
      {/if}
    </section>
  {:else}
    <section class="panel" role="status">
      <div class="done">
        {#if recorded}
          <span class="check" aria-hidden="true">
            <svg
              width="26"
              height="26"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="3"
              stroke-linecap="round"
              stroke-linejoin="round"><path d="M20 6 9 17l-5-5"></path></svg
            >
          </span>
          <div class="text">
            <div class="title">
              {view.outcome === "queued" ? "Queued" : "Recorded"}
              {actionName(recorded.action)}
            </div>
            <div class="sub muted">
              {(view.card ?? recorded.card).name}{view.card?.spoolId
                ? ` · #${view.card.spoolId}`
                : ""}
            </div>
          </div>
          <button type="button" class="small" onclick={onundo}>Undo</button>
        {:else}
          <p class="message {view.tone}">{view.message ?? view.card?.name ?? ""}</p>
        {/if}
      </div>
      {#if recorded && view.message && view.message !== `Recorded ${actionName(recorded.action)}.`}
        <p class="note message {view.tone}">{view.message}</p>
      {/if}
      <button type="button" class="next" aria-label="Scan next" onclick={onnext}>
        Ready for the next spool
        {#if view.countdown}<CountdownBar countdown={view.countdown} />{/if}
      </button>
    </section>
  {/if}
</div>

<style>
  .ready-row {
    display: flex;
    align-items: stretch;
    gap: 10px;
  }

  .ready {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 18px;
    padding: 22px 20px;
    border-radius: 20px;
    border: 1px solid var(--line);
    background: var(--surface);
    overflow: hidden;
  }

  .target {
    position: relative;
    width: 64px;
    height: 64px;
    flex: none;
  }

  /* The same pulse as the waiting screen's target, sized to this icon. */
  .ping {
    position: absolute;
    inset: -15px;
    border-radius: 50%;
    border: 2px solid var(--accent);
    animation: ping 2s ease-out infinite;
  }

  .ping.b {
    animation-delay: 1s;
  }

  .busy .ping {
    animation-duration: 0.8s;
  }

  @keyframes ping {
    0% {
      transform: scale(0.7);
      opacity: 0.7;
    }
    100% {
      transform: scale(1.25);
      opacity: 0;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .ping {
      animation: none;
      opacity: 0.4;
    }
  }

  .icon {
    position: relative;
    width: 64px;
    height: 64px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: var(--chip);
  }

  .title {
    display: block;
    font-family: var(--font-head);
    font-size: 21px;
    font-weight: 600;
  }

  .sub {
    display: block;
    margin-top: 2px;
    font-size: 14px;
    line-height: 1.35;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .ready .sub {
    white-space: normal;
  }

  .panel {
    border-radius: 20px;
    border: 1px solid var(--line);
    background: var(--surface);
    overflow: hidden;
  }

  .panel.found {
    border: 2px solid var(--accent);
  }

  .inner {
    padding: 16px 16px 14px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .spool {
    display: flex;
    align-items: center;
    gap: 14px;
  }

  h3 {
    margin: 6px 0 0;
    font-size: 21px;
    font-weight: 700;
    line-height: 1.2;
  }

  .spool p {
    margin: 2px 0 0;
    font-size: 14px;
  }

  .panel :global(.key) {
    min-height: 64px;
    background: var(--bg);
  }

  .panel :global(.key.primary) {
    background: var(--accent);
  }

  .found :global(.countdown) {
    gap: 0;
  }

  .found :global(.track) {
    border-radius: 0;
  }

  .found :global(.fill) {
    background: var(--accent);
    border-radius: 0;
  }

  .done {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 18px 16px 16px 20px;
  }

  .check {
    width: 48px;
    height: 48px;
    flex: none;
    border-radius: 50%;
    background: var(--okdot);
    color: #ffffff;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .done .text {
    flex: 1;
    min-width: 0;
  }

  .done .title {
    font-size: 20px;
  }

  .note {
    margin: 0 16px 14px;
  }

  .next {
    width: 100%;
    min-height: 48px;
    padding: 12px 20px;
    border: 0;
    border-top: 1px solid var(--line);
    border-radius: 0;
    background: transparent;
    font-size: 14px;
    font-weight: 500;
    color: var(--muted);
    display: flex;
    align-items: center;
    gap: 10px;
    text-align: left;
  }

  .next :global(.countdown) {
    flex: 1;
  }
</style>
