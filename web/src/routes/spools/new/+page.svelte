<script lang="ts">
  import { goto } from "$app/navigation";
  import { addSpool, createProduct, listProducts } from "#lib/api/admin.ts";
  import { describeError } from "#lib/api/errors.ts";
  import type { Product } from "#lib/api/types.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import Forbidden from "#lib/components/Forbidden.svelte";
  import { hexText } from "#lib/format.ts";
  import { blankIsNull, emptyEntry, entryProblem, rgbaOf } from "#lib/manual-entry.ts";

  let products = $state<Product[] | null>(null);
  let failure = $state<string | null>(null);
  let entry = $state(emptyEntry());
  let problem = $state<string | null>(null);
  let busy = $state(false);

  const types = $derived([...new Set((products ?? []).map((p) => p.filament_type))].sort());

  async function load(): Promise<void> {
    try {
      products = await listProducts();
      if (products.length === 0) entry.choice = "new";
    } catch (error) {
      failure = describeError(error);
    }
  }

  $effect(() => {
    if (session.can("editor")) void load();
  });

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    problem = entryProblem(entry);
    if (problem) return;
    busy = true;
    try {
      let productId = entry.productId;
      if (entry.choice === "new") {
        const product = await createProduct({
          display_name: entry.name.trim(),
          filament_type: entry.type.trim(),
          color_rgba: rgbaOf(entry.color),
        });
        // Use it from now on, so a failed spool save does not create it twice.
        products = [...(products as Product[]), product];
        entry.choice = "existing";
        entry.productId = product.id;
        productId = product.id;
      }
      const spool = await addSpool({
        product_id: productId as number,
        location: blankIsNull(entry.location),
        notes: blankIsNull(entry.notes),
      });
      await goto(`/spools/${spool.id}`);
    } catch (error) {
      problem = describeError(error);
    } finally {
      busy = false;
    }
  }
</script>

<svelte:head><title>Add a spool by hand · Filament Tracker</title></svelte:head>

{#if !session.can("editor")}
  <Forbidden />
{:else}
  <div class="page">
    <a class="back" href="/spools">
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.2"
        aria-hidden="true"
      >
        <path d="m15 18-6-6 6-6"></path>
      </svg>
      Spools
    </a>
    <div class="pagehead">
      <div>
        <h1>Add a spool by hand</h1>
        <p>
          For a spool whose tag cannot be read yet, such as TPU in a foil bag. It is recorded as
          new, and linked to its tag the first time the tag is scanned.
        </p>
      </div>
    </div>

    {#if failure}
      <p role="alert" class="error">{failure}</p>
    {:else if !products}
      <p class="muted">Loading…</p>
    {:else}
      <form class="card" onsubmit={submit} novalidate>
        <fieldset>
          <legend class="label">Product</legend>
          <div class="choice">
            <label class="radio">
              <input
                type="radio"
                name="choice"
                value="existing"
                disabled={products.length === 0}
                bind:group={entry.choice}
              />
              One I already have
            </label>
            <label class="radio">
              <input type="radio" name="choice" value="new" bind:group={entry.choice} />
              A new product
            </label>
          </div>

          {#if entry.choice === "existing"}
            <label class="field">
              Product
              <select bind:value={entry.productId}>
                <option value={null} disabled>Choose a product</option>
                {#each products as product (product.id)}
                  <option value={product.id}
                    >{product.display_name} · {product.filament_type} · #{hexText(
                      product.color_rgba,
                    )}</option
                  >
                {/each}
              </select>
            </label>
          {:else}
            <label class="field">
              Name
              <input
                type="text"
                maxlength="100"
                placeholder="TPU 95A HF Black"
                bind:value={entry.name}
              />
            </label>
            <div class="row">
              <label class="field">
                Filament type
                <input
                  type="text"
                  maxlength="32"
                  list="known-types"
                  placeholder="PLA"
                  bind:value={entry.type}
                />
              </label>
              <datalist id="known-types">
                {#each types as type (type)}<option value={type}></option>{/each}
              </datalist>
              <label class="field">
                Color
                <span class="color">
                  <input type="color" bind:value={entry.color} />
                  <span class="mono">{entry.color.toUpperCase()}</span>
                </span>
              </label>
            </div>
            <p class="muted hint">
              Added as a provisional product, merged into the real one when one of its tags is
              scanned.
            </p>
          {/if}
        </fieldset>

        <label class="field">
          Location <span class="muted">(optional)</span>
          <input type="text" maxlength="100" bind:value={entry.location} />
        </label>
        <label class="field">
          Notes <span class="muted">(optional)</span>
          <textarea maxlength="2000" bind:value={entry.notes}></textarea>
        </label>

        {#if problem}<p role="alert" class="error">{problem}</p>{/if}
        <div class="actions">
          <button type="submit" class="primary" disabled={busy}>Add spool</button>
          <a class="button" href="/spools">Cancel</a>
        </div>
      </form>
    {/if}
  </div>
{/if}

<style>
  .back {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: var(--muted);
    font-size: 14px;
    font-weight: 600;
    min-height: 44px;
    align-self: flex-start;
  }

  form {
    max-width: 640px;
  }

  fieldset {
    margin: 0;
    padding: 0;
    border: 0;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  legend {
    margin-bottom: 12px;
  }

  .choice {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 20px;
  }

  .radio {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    min-height: 44px;
    font-weight: 500;
  }

  .radio input {
    width: 20px;
    height: 20px;
    min-height: 0;
    accent-color: var(--accent);
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 13px;
    font-weight: 600;
    color: var(--muted);
    flex: 1 1 200px;
  }

  .field input,
  .field select,
  .field textarea {
    color: var(--text);
  }

  .row {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
  }

  .color {
    display: flex;
    align-items: center;
    gap: 10px;
    color: var(--text);
  }

  .color input {
    width: 64px;
    padding: 4px;
  }

  .hint {
    margin: 0;
    font-size: 13px;
  }

  .actions {
    display: flex;
    gap: 10px;
  }
</style>
