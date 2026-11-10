<script lang="ts">
  // The phone app's start screen: the RollCall intro animation while the app loads its
  // pairing and first hears from the server. Shown alone, so the animation's own styles
  // (global class names inside the SVG) touch nothing else. To change the animation,
  // replace the file: the screen times itself from it.
  import intro from "#lib/assets/rollcall-intro-roll.svg?raw";
  import { cycleMs, remainingMs } from "#lib/start-screen.ts";

  interface Props {
    /** Whether the app is ready to show its first screen. */
    ready: boolean;
    /** Called once, when the start screen is done. */
    ondone: () => void;
  }

  let { ready, ondone }: Props = $props();

  let logo: HTMLDivElement;
  const opened = Date.now();
  let cycle: number | null = null;
  let finished = false;

  // Runs once the logo is in the page, and again whenever `ready` changes.
  $effect(() => {
    cycle ??= cycleMs(logo);
    const wait = remainingMs(Date.now() - opened, cycle, ready);
    const timer = setTimeout(() => {
      if (finished) return;
      finished = true;
      ondone();
    }, wait);
    return () => clearTimeout(timer);
  });
</script>

<main class="start" aria-busy="true">
  <!-- A static file from this repo, not user content. -->
  <div class="logo" bind:this={logo}>{@html intro}</div>
</main>

<style>
  .start {
    min-height: 100vh;
    min-height: 100dvh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg);
  }

  .logo {
    width: min(92vw, 560px);
  }

  .logo :global(svg) {
    display: block;
    width: 100%;
    height: auto;
  }

  /* The intro's words are drawn dark for the logo's cream; on the dark theme, light them. */
  :global(:root[data-theme="dark"]) .logo :global(.roll),
  :global(:root[data-theme="dark"]) .logo :global(.call) {
    fill: #fff7f5;
  }

  :global(:root[data-theme="dark"]) .logo :global(.tag1),
  :global(:root[data-theme="dark"]) .logo :global(.tag2) {
    fill: #c9aeb2;
  }
</style>
