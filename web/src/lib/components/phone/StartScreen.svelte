<script lang="ts">
  // The phone app's start screen: the Rollcall logo animation while the app loads its
  // pairing and first hears from the server. Shown alone, so the animation's own styles
  // (global class names inside the SVG) touch nothing else.
  import loading from "#lib/assets/rollcall-loading.svg?raw";
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

<main class="start">
  <!-- A static file from this repo, not user content. -->
  <div class="logo" bind:this={logo}>{@html loading}</div>
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
    width: 160px;
    height: 160px;
  }

  .logo :global(svg) {
    width: 100%;
    height: 100%;
  }
</style>
