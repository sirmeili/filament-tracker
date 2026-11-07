<script lang="ts">
  /** Turns the Delivery list (unpacking a delivery) on and off. */
  interface Props {
    on: boolean;
    ontoggle: () => void;
  }

  let { on, ontoggle }: Props = $props();
</script>

<button
  type="button"
  class="toggle"
  class:on
  aria-pressed={on}
  title="Unpacking a delivery: keep a list of the spools you scan"
  onclick={ontoggle}
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
    <path d="M21 8 12 3 3 8v8l9 5 9-5z"></path>
    <path d="M3 8l9 5 9-5M12 13v8"></path>
  </svg>
  Delivery
</button>

<style>
  .toggle {
    min-width: 64px;
    min-height: 64px;
    flex: none;
    padding: 8px 12px;
    border-radius: 16px;
    border: 1px solid var(--line);
    background: var(--surface);
    color: var(--muted);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .toggle.on {
    background: var(--text);
    border-color: var(--text);
    color: var(--bg);
  }
</style>
