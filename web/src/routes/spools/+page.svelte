<script lang="ts">
  import { describeError } from "#lib/api/errors.ts";
  import { getInventory, listSpools, moveSpools } from "#lib/api/stock.ts";
  import type { Page, ProductSummary, SpoolRow, SpoolState } from "#lib/api/types.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import MoveBar from "#lib/components/spools/MoveBar.svelte";
  import SpoolTable from "#lib/components/spools/SpoolTable.svelte";
  import { page } from "$app/state";
  import { ALL_TYPES, filamentTypes } from "#lib/inventory.ts";
  import { countText, knownLocations, PAGE_SIZE, rangeText, STATE_FILTERS } from "#lib/spools.ts";

  /** Wait this long after the last keystroke before searching. */
  const SEARCH_DELAY_MS = 250;

  let inventory = $state<ProductSummary[]>([]);
  let result = $state<Page<SpoolRow> | null>(null);
  let failure = $state<string | null>(null);
  let notice = $state<string | null>(null);

  let stateFilter = $state<SpoolState | "all">("all");
  let type = $state(ALL_TYPES);
  // Inventory's "View spools" opens this page searched for the product (?q=).
  let search = $state(page.url?.searchParams.get("q") ?? "");
  let offset = $state(0);
  let reloads = $state(0);

  let selected = $state(new Set<number>());
  let moving = $state(false);

  const canEdit = $derived(session.can("editor"));
  const spools = $derived(result?.items ?? []);

  async function loadCounts(): Promise<void> {
    try {
      inventory = await getInventory();
    } catch {
      // The counts and the type list are extras; the table still works without them.
    }
  }

  $effect(() => {
    void loadCounts();
  });

  // Reload whenever a filter, the page or `reloads` changes; typing waits for a pause.
  $effect(() => {
    const query = {
      states: stateFilter === "all" ? [] : [stateFilter],
      type: type === ALL_TYPES ? undefined : type,
      q: search,
      limit: PAGE_SIZE,
      offset,
    };
    void reloads;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        result = await listSpools(query, controller.signal);
        failure = null;
      } catch (error) {
        if (!controller.signal.aborted) failure = describeError(error);
      }
    }, SEARCH_DELAY_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  });

  function filter(apply: () => void): void {
    apply();
    offset = 0;
    selected = new Set();
  }

  function toggle(id: number): void {
    const next = new Set(selected);
    if (!next.delete(id)) next.add(id);
    selected = next;
  }

  async function move(location: string | null): Promise<void> {
    moving = true;
    notice = null;
    try {
      const moved = await moveSpools([...selected], location);
      notice = location
        ? `Moved ${moved.length} to ${location}.`
        : `Cleared the location of ${moved.length}.`;
      selected = new Set();
      reloads += 1;
    } catch (error) {
      notice = describeError(error);
    } finally {
      moving = false;
    }
  }
</script>

<svelte:head><title>Spools · RollCall</title></svelte:head>

<div class="page">
  <div class="pagehead">
    <div>
      <h1>Spools</h1>
      {#if inventory.length}<p>{countText(inventory)}</p>{/if}
    </div>
    {#if canEdit}
      <a class="button primary" href="/spools/new">
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.4"
          aria-hidden="true"
        >
          <path d="M12 5v14M5 12h14"></path>
        </svg>
        Add spool by hand
      </a>
    {/if}
  </div>

  <div class="toolbar">
    <label class="search">
      <span class="sr-only">Search spools</span>
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        aria-hidden="true"
      >
        <circle cx="11" cy="11" r="7"></circle>
        <path d="m20 20-3.5-3.5"></path>
      </svg>
      <input
        type="search"
        placeholder="Product, type, location or notes"
        maxlength="100"
        value={search}
        oninput={(event) => filter(() => (search = event.currentTarget.value))}
      />
    </label>
    <div class="toolbar chips" role="group" aria-label="Filter by state">
      {#each STATE_FILTERS as option (option.value)}
        <button
          type="button"
          class="chip"
          aria-pressed={stateFilter === option.value}
          onclick={() => filter(() => (stateFilter = option.value))}>{option.label}</button
        >
      {/each}
    </div>
    <label class="type">
      Type
      <select value={type} onchange={(event) => filter(() => (type = event.currentTarget.value))}>
        {#each filamentTypes(inventory) as option (option)}
          <option value={option}>{option}</option>
        {/each}
      </select>
    </label>
  </div>

  {#if notice}<p role="status" class="muted">{notice}</p>{/if}

  {#if canEdit && selected.size > 0}
    <MoveBar
      count={selected.size}
      locations={knownLocations(spools)}
      busy={moving}
      onmove={move}
      onclear={() => (selected = new Set())}
    />
  {/if}

  {#if failure}
    <p role="alert" class="error">{failure}</p>
  {:else if !result}
    <p class="muted">Loading…</p>
  {:else}
    <SpoolTable {spools} selected={canEdit ? selected : null} ontoggle={toggle} />
    <div class="pager">
      <span>{rangeText(result.offset, spools.length, result.total)}</span>
      <div class="toolbar">
        <button
          type="button"
          disabled={offset === 0}
          onclick={() => (offset = Math.max(0, offset - PAGE_SIZE))}>Previous</button
        >
        <button
          type="button"
          disabled={offset + PAGE_SIZE >= result.total}
          onclick={() => (offset += PAGE_SIZE)}>Next</button
        >
      </div>
    </div>
  {/if}
</div>

<style>
  .search {
    position: relative;
    flex: 1 1 260px;
    display: flex;
  }

  .search svg {
    position: absolute;
    left: 14px;
    top: 13px;
    color: var(--muted);
  }

  .search input {
    flex: 1;
    padding-left: 42px;
    background: var(--surface);
  }

  .chips {
    gap: 8px;
  }

  .type {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    font-weight: 600;
    color: var(--muted);
  }

  .type select {
    min-width: 110px;
    background: var(--surface);
  }

  .pager {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    color: var(--muted);
    font-size: 14px;
  }

  .pager .toolbar {
    gap: 8px;
  }
</style>
