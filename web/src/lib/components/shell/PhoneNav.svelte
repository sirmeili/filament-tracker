<script lang="ts">
  // The phone layout's bottom bar (docs/mockups/mobile-web/): Menu at the left, Scan in the
  // centre (only in the Android app) and the signed-in user at the right, who opens Account.
  import type { Me } from "#lib/api/types.ts";
  import ScanIcon from "#lib/components/phone/ScanIcon.svelte";
  import MenuSheet from "#lib/components/shell/MenuSheet.svelte";
  import { ACCOUNT_PATH, menuGroups, navItemFor } from "#lib/nav.ts";

  interface Props {
    user: Me;
    pathname: string;
    reviewCount: number;
    /** In the phone app: show the Scan button. */
    scan?: boolean;
  }

  let { user, pathname, reviewCount, scan = false }: Props = $props();

  let open = $state(false);
  let menuButton: HTMLButtonElement;
  const groups = $derived(menuGroups(user.role));

  /** Close the menu and give the focus back to the Menu button. */
  function close(): void {
    open = false;
    menuButton.focus();
  }

  // A new page closes the menu.
  $effect(() => {
    void pathname;
    open = false;
  });
</script>

{#if open}
  <MenuSheet
    main={groups.main}
    admin={groups.admin}
    current={navItemFor(pathname)}
    badges={{ "/review": reviewCount }}
    onclose={close}
  />
{/if}

<nav aria-label="App" class="bar">
  <button
    type="button"
    class="end start"
    aria-expanded={open}
    aria-controls="menu-sheet"
    bind:this={menuButton}
    onclick={() => (open ? close() : (open = true))}
  >
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2.2"
      stroke-linecap="round"
      aria-hidden="true"
    >
      {#if open}
        <path d="M6 6l12 12M18 6 6 18"></path>
      {:else}
        <path d="M4 7h16M4 12h16M4 17h16"></path>
      {/if}
    </svg>
    {open ? "Close" : "Menu"}
    {#if reviewCount > 0 && !open}<span class="dot" aria-hidden="true"></span>{/if}
  </button>

  {#if scan}
    <a class="scan" href="/scan"
      ><span class="fab" aria-hidden="true"><ScanIcon size={30} /></span>Scan</a
    >
  {:else}
    <span></span>
  {/if}

  <a
    class="end finish"
    href={ACCOUNT_PATH}
    aria-current={pathname === ACCOUNT_PATH ? "page" : undefined}
  >
    <span class="initial" aria-hidden="true">{user.username.charAt(0).toUpperCase()}</span>
    {user.username}
  </a>
</nav>

<style>
  .bar {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 42;
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    align-items: end;
    padding: 8px 14px calc(14px + env(safe-area-inset-bottom, 0px));
    border-top: 1px solid var(--line);
    background: var(--surface);
  }

  .end {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    min-width: 64px;
    min-height: 48px;
    padding: 0 6px;
    border: 0;
    background: transparent;
    color: var(--muted);
    font-size: 12px;
    font-weight: 600;
  }

  .start {
    justify-self: start;
  }

  .finish {
    justify-self: end;
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .end[aria-expanded="true"],
  .end[aria-current="page"] {
    color: var(--text);
  }

  .dot {
    position: absolute;
    top: 4px;
    right: 18px;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent);
  }

  .scan {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    margin-top: -30px;
    color: var(--text);
    font-size: 12px;
    font-weight: 700;
  }

  .fab {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--accent);
    color: var(--onaccent);
    box-shadow:
      0 0 0 5px var(--surface),
      0 4px 14px rgba(0, 0, 0, 0.25);
  }

  .initial {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--chip);
    color: var(--text);
    font-size: 13px;
    font-weight: 700;
  }

  .end[aria-current="page"] .initial {
    background: var(--text);
    color: var(--bg);
  }
</style>
