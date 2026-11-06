<script lang="ts">
  import { selectionText } from "#lib/spools.ts";

  interface Props {
    count: number;
    locations: string[];
    busy: boolean;
    onmove: (location: string | null) => void;
    onclear: () => void;
  }

  let { count, locations, busy, onmove, onclear }: Props = $props();
  let location = $state("");

  function submit(event: SubmitEvent): void {
    event.preventDefault();
    onmove(location.trim() || null);
  }
</script>

<form class="bar" onsubmit={submit} aria-label="Move selected spools">
  <strong>{selectionText(count)}</strong>
  <span class="grow"></span>
  <label>
    Move to
    <input
      type="text"
      list="known-locations"
      maxlength="100"
      placeholder="Blank clears it"
      bind:value={location}
    />
  </label>
  <datalist id="known-locations">
    {#each locations as known (known)}<option value={known}></option>{/each}
  </datalist>
  <button type="submit" class="primary" disabled={busy}>Move</button>
  <button type="button" onclick={onclear}>Clear</button>
</form>

<style>
  .bar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    border-radius: 12px;
    background: var(--text);
    color: var(--bg);
  }

  strong {
    font-size: 15px;
  }

  .grow {
    flex: 1;
  }

  label {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    font-weight: 600;
  }

  input {
    min-width: 180px;
    background: var(--surface);
  }
</style>
