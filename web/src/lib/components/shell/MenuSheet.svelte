<script lang="ts">
  // The phone layout's menu (docs/mockups/mobile-web/PhoneMenu.dc.html): a sheet that rises
  // from the bottom over a dimmed page. Escape, the dimmed page or a page link closes it.
  import NavIcon from "#lib/components/shell/NavIcon.svelte";
  import type { NavItem } from "#lib/nav.ts";

  interface Props {
    main: NavItem[];
    admin: NavItem[];
    current: NavItem | undefined;
    /** A count shown next to a page, by href; 0 hides it. */
    badges?: Record<string, number>;
    onclose: () => void;
  }

  let { main, admin, current, badges = {}, onclose }: Props = $props();

  let sheet: HTMLDivElement;

  function links(): HTMLAnchorElement[] {
    return [...sheet.querySelectorAll("a")];
  }

  // Start on the current page's link, or the first one.
  $effect(() => {
    const all = links();
    (all.find((link) => link.getAttribute("aria-current") === "page") ?? all[0])?.focus();
  });

  /** Escape closes; Tab stays among the menu's links. */
  function keydown(event: KeyboardEvent): void {
    if (event.key === "Escape") {
      event.preventDefault();
      onclose();
      return;
    }
    if (event.key !== "Tab") return;
    const all = links();
    const first = all[0];
    const last = all[all.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
</script>

{#snippet link(item: NavItem, small: boolean)}
  {@const count = badges[item.href] ?? 0}
  <a
    class="item"
    class:small
    href={item.href}
    aria-current={item === current ? "page" : undefined}
    aria-label={count > 0 ? `${item.label}, ${count} waiting` : undefined}
    onclick={onclose}
    ><NavIcon href={item.href} />{item.label}{#if count > 0}<span class="badge" aria-hidden="true"
        >{count}</span
      >{/if}</a
  >
{/snippet}

<button type="button" class="dim" aria-label="Close the menu" tabindex="-1" onclick={onclose}
></button>
<div
  class="sheet"
  id="menu-sheet"
  role="dialog"
  aria-modal="true"
  aria-label="Menu"
  tabindex="-1"
  bind:this={sheet}
  onkeydown={keydown}
>
  <span class="grip" aria-hidden="true"></span>
  <nav aria-label="Pages" class="pages">
    {#each main as item (item.href)}{@render link(item, false)}{/each}
  </nav>
  {#if admin.length > 0}
    <div class="label">Admin</div>
    <nav aria-label="Admin pages" class="admin">
      {#each admin as item (item.href)}{@render link(item, true)}{/each}
    </nav>
  {/if}
</div>

<style>
  .dim {
    position: fixed;
    inset: 0;
    z-index: 40;
    border: 0;
    border-radius: 0;
    padding: 0;
    min-height: 0;
    background: rgba(0, 0, 0, 0.45);
  }

  .sheet {
    position: fixed;
    left: 0;
    right: 0;
    bottom: var(--bottom-bar, 84px);
    z-index: 41;
    display: flex;
    flex-direction: column;
    gap: 14px;
    max-height: calc(100dvh - var(--bottom-bar, 84px) - 24px);
    overflow-y: auto;
    padding: 10px 16px 18px;
    border-radius: 24px 24px 0 0;
    background: var(--surface);
    outline: none;
  }

  .grip {
    align-self: center;
    width: 40px;
    height: 5px;
    border-radius: 999px;
    background: var(--line);
  }

  .pages {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  /* An odd last page (Activity) spans both columns. */
  .pages :global(.item:last-child:nth-child(odd)) {
    grid-column: span 2;
  }

  .admin {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
  }

  .item {
    display: flex;
    align-items: center;
    gap: 12px;
    min-height: 56px;
    padding: 0 14px;
    border-radius: 14px;
    border: 1px solid var(--line);
    background: var(--bg);
    font-size: 16px;
    font-weight: 600;
    box-sizing: border-box;
  }

  .item.small {
    flex-direction: column;
    justify-content: center;
    gap: 4px;
    min-height: 68px;
    font-size: 14px;
  }

  .item[aria-current="page"] {
    background: var(--text);
    border-color: var(--text);
    color: var(--bg);
  }

  .badge {
    margin-left: auto;
    padding: 1px 8px;
    border-radius: 999px;
    background: var(--accent);
    color: var(--onaccent);
    font-size: 12px;
    font-weight: 700;
  }

  .label {
    margin: 2px 4px -4px;
  }
</style>
