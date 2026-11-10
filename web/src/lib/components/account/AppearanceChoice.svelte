<script lang="ts">
  // Account › Appearance (docs/mockups/mobile-web/PhoneAccount.dc.html): Light, Dark or
  // System, saved on this device only.
  import type { Theme, ThemeChoice } from "#lib/theme.svelte.ts";

  let { theme }: { theme: Theme } = $props();

  const OPTIONS: { choice: ThemeChoice; label: string }[] = [
    { choice: "light", label: "Light" },
    { choice: "dark", label: "Dark" },
    { choice: "system", label: "System" },
  ];
</script>

<section class="card" aria-labelledby="ap-h">
  <h2 id="ap-h" class="label">Appearance</h2>
  <div class="seg" role="group" aria-label="Appearance">
    {#each OPTIONS as option (option.choice)}
      <button
        type="button"
        aria-pressed={theme.choice === option.choice}
        onclick={() => theme.set(option.choice)}
      >
        <svg
          width="22"
          height="22"
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
        {option.label}
      </button>
    {/each}
  </div>
  <p class="muted">
    Saved on this device. Your phone and computer each keep their own. System follows the device's
    own setting.
  </p>
</section>

<style>
  section {
    max-width: 560px;
  }

  h2,
  p {
    margin: 0;
  }

  p {
    font-size: 13px;
  }

  .seg {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 4px;
    padding: 4px;
    border-radius: 14px;
    background: var(--chip);
  }

  button {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 6px;
    min-height: 64px;
    border: 0;
    border-radius: 11px;
    background: transparent;
    color: var(--muted);
    font-size: 14px;
    font-weight: 600;
  }

  button[aria-pressed="true"] {
    background: var(--surface);
    color: var(--text);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.18);
  }
</style>
