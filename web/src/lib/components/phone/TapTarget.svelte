<script lang="ts">
  import ScanIcon from "#lib/components/phone/ScanIcon.svelte";

  /** The waiting screen's target: where to hold the spool. `busy` while a tag is looked up. */
  let { busy = false }: { busy?: boolean } = $props();
</script>

<div class="waiting">
  <div class="target" class:busy aria-hidden="true">
    <span class="dash"></span>
    <span class="ping"></span>
    <span class="ping b"></span>
    <span class="core"></span>
    <span class="icon"><ScanIcon size={60} /></span>
  </div>
  {#if busy}
    <h2 role="status">Looking it up…</h2>
  {:else}
    <div>
      <h2>Hold a spool to the back of your phone</h2>
      <p class="muted">Either side of the spool works, even through a sealed box.</p>
    </div>
  {/if}
</div>

<style>
  .waiting {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 26px;
    padding: 0 28px;
    text-align: center;
  }

  .target {
    position: relative;
    width: 240px;
    height: 240px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .dash,
  .ping,
  .core {
    position: absolute;
    border-radius: 50%;
  }

  .dash {
    inset: 0;
    border: 1.5px dashed var(--line);
  }

  .ping {
    inset: 40px;
    border: 2px solid var(--accent);
    animation: ping 2s ease-out infinite;
  }

  .ping.b {
    animation-delay: 1s;
  }

  .busy .ping {
    animation-duration: 0.8s;
  }

  .core {
    inset: 66px;
    background: var(--surface);
    border: 2px solid var(--text);
  }

  .icon {
    position: relative;
    display: flex;
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

  h2 {
    margin: 0;
    font-size: 26px;
    font-weight: 600;
    line-height: 1.2;
  }

  p {
    margin: 10px 0 0;
    font-size: 15px;
    line-height: 1.45;
  }
</style>
