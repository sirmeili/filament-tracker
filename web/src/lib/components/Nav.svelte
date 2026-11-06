<script lang="ts">
  import type { NavItem } from "#lib/nav.ts";

  interface Props {
    items: NavItem[];
    current: NavItem | undefined;
    /** A count shown next to a page's link, by href; 0 hides it. */
    badges?: Record<string, number>;
  }

  let { items, current, badges = {} }: Props = $props();
</script>

<nav aria-label="Main">
  <ul>
    {#each items as item (item.href)}
      {@const count = badges[item.href] ?? 0}
      <li>
        <a
          href={item.href}
          aria-current={item === current ? "page" : undefined}
          aria-label={count > 0 ? `${item.label}, ${count} waiting` : undefined}
          >{item.label}{#if count > 0}<span class="badge" aria-hidden="true">{count}</span>{/if}</a
        >
      </li>
    {/each}
  </ul>
</nav>

<style>
  nav {
    flex: 1 1 auto;
  }

  ul {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  a {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    min-height: 44px;
    padding: 0 14px;
    border-radius: 8px;
    color: var(--muted);
    font-weight: 500;
    font-size: 15px;
  }

  a:hover {
    background: var(--chip);
    color: var(--text);
  }

  a[aria-current="page"] {
    background: var(--text);
    color: var(--bg);
  }

  .badge {
    background: var(--accent);
    color: var(--onaccent);
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
    padding: 1px 7px;
  }
</style>
