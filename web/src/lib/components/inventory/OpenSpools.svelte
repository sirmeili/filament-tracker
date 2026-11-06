<script lang="ts">
  import type { OpenSpool } from "#lib/api/types.ts";
  import PctBar from "#lib/components/ui/PctBar.svelte";
  import { spoolLabel } from "#lib/inventory.ts";

  /** One % bar per open spool, each linking to the spool. */
  let { spools }: { spools: OpenSpool[] } = $props();
</script>

<ul>
  {#each spools as spool (spool.id)}
    <li>
      <a href="/spools/{spool.id}" aria-label={spoolLabel(spool.remaining_pct)}>
        <PctBar pct={spool.remaining_pct} low={spool.nearly_out} />
      </a>
    </li>
  {/each}
</ul>

<style>
  ul {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  a {
    display: flex;
    align-items: center;
    min-height: 24px;
  }
</style>
