<script lang="ts">
  import type { TagOut } from "#lib/api/types.ts";
  import { shortDate } from "#lib/format.ts";
  import { tagFields } from "#lib/tag-data.ts";

  /** A spool has up to two tags; the first readable one describes it. */
  let { tags }: { tags: TagOut[] } = $props();

  const fields = $derived(tagFields(tags.find((t) => t.decoded)?.decoded ?? null));
</script>

<section class="card" aria-labelledby="tag-h">
  <h2 id="tag-h" class="label">Tag data</h2>
  {#if tags.length === 0}
    <p class="muted">No tag scanned yet. This spool was added by hand.</p>
  {:else}
    {#if fields.length}
      <dl class="kv">
        {#each fields as field (field.label)}
          <div>
            <dt>{field.label}</dt>
            <dd>{field.value}</dd>
          </div>
        {/each}
      </dl>
    {:else}
      <p class="muted">The tag could not be decoded.</p>
    {/if}
    <ul class="tags">
      {#each ["A", "B"] as name, index (name)}
        <li>
          <span>Tag {name}</span>
          <span>
            {tags[index] ? `first seen ${shortDate(tags[index].first_seen_at)}` : "not scanned yet"}
          </span>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .kv {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px 16px;
    margin: 0;
  }

  dt {
    font-size: 12px;
    color: var(--muted);
    font-weight: 500;
  }

  dd {
    margin: 2px 0 0;
    font-family: var(--font-mono);
    font-size: 14px;
    font-weight: 500;
  }

  .tags {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin: 0;
    padding: 12px 0 0;
    list-style: none;
    border-top: 1px solid var(--line);
    font-size: 13px;
    color: var(--muted);
  }

  .tags li {
    display: flex;
    justify-content: space-between;
    gap: 8px;
  }

  p {
    margin: 0;
  }
</style>
