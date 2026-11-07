<script lang="ts">
  import CountdownBar from "#lib/components/phone/CountdownBar.svelte";
  import ScanCard from "#lib/components/phone/ScanCard.svelte";
  import { actionName, type FlowView } from "#lib/phone/scan-flow.ts";

  /** After a choice: the action recorded (or queued), Info, or a message, with what to do
   * next. The 3-second bar goes back to waiting on its own; Scan next goes back now. */
  interface Props {
    view: FlowView;
    onundo: () => void;
    onnext: () => void;
  }

  let { view, onundo, onnext }: Props = $props();

  const recorded = $derived(
    (view.outcome === "recorded" || view.outcome === "queued") && view.last && !view.last.undone
      ? view.last
      : null,
  );
  const spoolId = $derived(view.card?.spoolId ?? null);
</script>

<div class="middle" role="status">
  {#if recorded}
    <ScanCard card={view.card ?? recorded.card} done />
    <div class="what">
      <h2 class="big">{actionName(recorded.action)}</h2>
      <p class="name">{recorded.card.name}</p>
      {#if view.outcome === "queued"}
        <p class="muted">Queued · it will be sent when the server is back</p>
      {:else if view.message && view.message !== `Recorded ${actionName(recorded.action)}.`}
        <p class="message {view.tone}">{view.message}</p>
      {:else}
        <p class="muted">Recorded just now{spoolId ? ` · spool #${spoolId}` : ""}</p>
      {/if}
    </div>
  {:else}
    {#if view.card}<ScanCard card={view.card} />{/if}
    {#if view.outcome === "info" && view.card?.remainingPct != null}
      <p class="muted">{view.card.remainingPct}% left, as the AMS last reported</p>
    {/if}
    {#if view.message}<p class="message {view.tone}">{view.message}</p>{/if}
  {/if}
</div>

<div class="bottom">
  {#if view.countdown}
    <CountdownBar countdown={view.countdown} label="Ready for the next spool in 3 s" />
  {/if}
  {#if recorded || spoolId}
    <div class="pair">
      {#if recorded}<button type="button" onclick={onundo}>Undo</button>{/if}
      {#if spoolId}<a class="button" href="/spools/{spoolId}">View spool</a>{/if}
    </div>
  {/if}
  <button type="button" class="primary" onclick={onnext}>Scan next</button>
</div>

<style>
  .what {
    text-align: center;
  }

  .big {
    margin: 0;
    font-size: 40px;
    font-weight: 700;
    letter-spacing: -0.02em;
  }

  .name {
    margin: 8px 0 0;
    font-size: 17px;
    font-weight: 600;
  }

  .what p.muted {
    margin: 4px 0 0;
    font-size: 15px;
  }

  .pair {
    display: grid;
    grid-auto-flow: column;
    grid-auto-columns: minmax(0, 1fr);
    gap: 10px;
  }
</style>
