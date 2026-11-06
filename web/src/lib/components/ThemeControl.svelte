<script lang="ts">
  import type { Theme, ThemeChoice } from "#lib/theme.svelte.ts";

  let { theme }: { theme: Theme } = $props();

  const OPTIONS: { choice: ThemeChoice; label: string }[] = [
    { choice: "light", label: "Light theme" },
    { choice: "dark", label: "Dark theme" },
    { choice: "system", label: "Follow the device" },
  ];
</script>

<div class="seg" role="group" aria-label="Theme">
  {#each OPTIONS as option (option.choice)}
    <button
      type="button"
      aria-label={option.label}
      title={option.label}
      aria-pressed={theme.choice === option.choice}
      onclick={() => theme.set(option.choice)}
    >
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        aria-hidden="true"
      >
        {#if option.choice === "light"}
          <circle cx="12" cy="12" r="4"></circle>
          <path
            d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"
          ></path>
        {:else if option.choice === "dark"}
          <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"></path>
        {:else}
          <rect x="3" y="4" width="18" height="12" rx="2"></rect>
          <path d="M8 20h8M12 16v4"></path>
        {/if}
      </svg>
    </button>
  {/each}
</div>

<style>
  .seg {
    display: inline-flex;
    gap: 2px;
    padding: 2px;
    border: 1px solid var(--line);
    border-radius: 10px;
    background: var(--surface);
  }

  button {
    min-height: 40px;
    width: 40px;
    padding: 0;
    border: 0;
    border-radius: 8px;
    background: transparent;
    color: var(--muted);
  }

  button[aria-pressed="true"] {
    background: var(--text);
    color: var(--bg);
  }
</style>
