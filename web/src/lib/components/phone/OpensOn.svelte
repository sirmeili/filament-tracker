<script lang="ts">
  // Where this phone opens (Phone scanner in docs/SPEC.md): Inventory or Scan.
  import type { OpenOn } from "#lib/phone/pairing-store.ts";

  interface Props {
    /** The current choice; null when none was made yet. */
    value: OpenOn | null;
    onchoose: (value: OpenOn) => void | Promise<void>;
  }

  let { value, onchoose }: Props = $props();

  const CHOICES: { value: OpenOn; label: string; hint: string }[] = [
    { value: "stock", label: "Looking at stock", hint: "Opens on Inventory" },
    { value: "scan", label: "Scanning", hint: "Opens on Scan" },
  ];
</script>

<div class="choices" role="group" aria-label="This phone opens on">
  {#each CHOICES as choice (choice.value)}
    <button
      type="button"
      class:primary={value === choice.value}
      aria-pressed={value === choice.value}
      onclick={() => onchoose(choice.value)}
    >
      <span class="name">{choice.label}</span>
      <span class="hint">{choice.hint}</span>
    </button>
  {/each}
</div>

<style>
  .choices {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }

  button {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    padding: 14px 16px;
    text-align: left;
  }

  .name {
    font-weight: 600;
  }

  .hint {
    font-size: 0.85rem;
    opacity: 0.8;
  }
</style>
