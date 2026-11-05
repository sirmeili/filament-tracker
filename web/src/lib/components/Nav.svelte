<script lang="ts">
  import type { NavItem } from "#lib/nav.ts";

  interface Props {
    items: NavItem[];
    current: NavItem | undefined;
  }

  let { items, current }: Props = $props();
</script>

<nav aria-label="Main">
  <ul>
    {#each items as item (item.href)}
      <li>
        <a href={item.href} aria-current={item === current ? "page" : undefined}>{item.label}</a>
      </li>
    {/each}
  </ul>
</nav>

<style>
  ul {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  a {
    display: block;
    padding: 0.4rem 0.7rem;
    border-radius: var(--radius);
    color: var(--text);
    text-decoration: none;
  }

  a:hover {
    background: var(--surface-hover);
  }

  a[aria-current="page"] {
    background: var(--accent);
    color: var(--accent-text);
  }
</style>
