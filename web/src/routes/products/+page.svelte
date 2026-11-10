<script lang="ts">
  import { describeError } from "#lib/api/errors.ts";
  import { getInventory, updateProduct } from "#lib/api/stock.ts";
  import type { ProductSummary } from "#lib/api/types.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import ProductTable from "#lib/components/products/ProductTable.svelte";
  import { changesFor, type Draft, draftOf, draftProblem, unsavedText } from "#lib/products.ts";

  let items = $state<ProductSummary[] | null>(null);
  let drafts = $state<Record<number, Draft>>({});
  let failure = $state<string | null>(null);
  let saving = $state(false);
  let message = $state<string | null>(null);

  const canEdit = $derived(session.can("editor"));
  const changed = $derived(
    (items ?? []).filter((item) => {
      const draft = drafts[item.product.id];
      return draft !== undefined && changesFor(item.product, draft) !== null;
    }),
  );
  const invalid = $derived(Object.values(drafts).some((draft) => draftProblem(draft) !== null));

  function reset(next: ProductSummary[]): void {
    items = next;
    drafts = Object.fromEntries(next.map((item) => [item.product.id, draftOf(item.product)]));
  }

  async function load(): Promise<void> {
    failure = null;
    try {
      reset(await getInventory());
    } catch (error) {
      failure = describeError(error);
    }
  }

  $effect(() => {
    void load();
  });

  async function save(): Promise<void> {
    saving = true;
    message = null;
    const problems: string[] = [];
    for (const item of changed) {
      const changes = changesFor(item.product, drafts[item.product.id]);
      if (!changes) continue;
      try {
        await updateProduct(item.product.id, changes);
      } catch (error) {
        problems.push(`${item.product.display_name}: ${describeError(error)}`);
      }
    }
    try {
      const unsaved = problems.length ? { ...drafts } : null;
      reset(await getInventory());
      // Keep what could not be saved, so it can be fixed and saved again.
      if (unsaved) drafts = { ...drafts, ...unsaved };
    } catch (error) {
      problems.push(describeError(error));
    }
    message = problems.length ? `Not saved. ${problems.join(" ")}` : "Saved";
    saving = false;
  }
</script>

<svelte:head><title>Products · RollCall</title></svelte:head>

<div class="page">
  <div class="pagehead">
    <div>
      <h1>Products</h1>
      <p>
        Created automatically from the first tag of each product. Rename them and set when each
        counts as low on stock or nearly out.
      </p>
    </div>
    {#if canEdit && items}
      <div class="save">
        {#if message && message !== "Saved"}
          <span role="status" class="error">{message}</span>
        {:else if changed.length}
          <span class="muted">{unsavedText(changed.length)}</span>
        {:else if message}
          <span role="status" class="muted">{message}</span>
        {/if}
        <button
          type="button"
          class="primary"
          disabled={saving || invalid || changed.length === 0}
          onclick={save}>Save changes</button
        >
      </div>
    {/if}
  </div>

  {#if failure}
    <p role="alert" class="error">{failure}</p>
  {:else if !items}
    <p class="muted">Loading…</p>
  {:else if items.length === 0}
    <p class="muted">No products yet. Scan a spool's tag to add its product.</p>
  {:else}
    <ProductTable {items} drafts={canEdit ? drafts : null} />
    <p class="muted foot">
      Low at: 0 turns the low-stock alert off. Nearly out: an open spool at or below this AMS % is
      marked nearly out. A product added by hand is merged into the real one when one of its tags is
      scanned.
    </p>
  {/if}
</div>

<style>
  .pagehead p {
    max-width: 640px;
  }

  .save {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px;
    font-size: 14px;
  }

  .foot {
    margin: 0;
    font-size: 13px;
  }
</style>
