<script lang="ts">
  import type { Me } from "#lib/api/types.ts";
  import Nav from "#lib/components/Nav.svelte";
  import ScanIcon from "#lib/components/phone/ScanIcon.svelte";
  import RollCallMark from "#lib/components/shell/RollCallMark.svelte";
  import { ACCOUNT_PATH, navItemFor, visibleNav } from "#lib/nav.ts";
  import { ROLE_LABELS } from "#lib/roles.ts";

  interface Props {
    user: Me;
    pathname: string;
    reviewCount: number;
    /** In the phone app: show the button back to Scan. */
    scan?: boolean;
  }

  let { user, pathname, reviewCount, scan = false }: Props = $props();
</script>

<header>
  <div class="inner">
    <a class="brand" href="/">
      <RollCallMark />
      RollCall
    </a>
    <Nav
      items={visibleNav(user.role)}
      current={navItemFor(pathname)}
      badges={{ "/review": reviewCount }}
    />
    <div class="end">
      {#if scan}
        <a class="scan" href="/scan" aria-label="Scan" title="Scan"><ScanIcon size={24} /></a>
      {/if}
      <a
        class="account"
        href={ACCOUNT_PATH}
        aria-current={pathname === ACCOUNT_PATH ? "page" : undefined}
        title="Account · {ROLE_LABELS[user.role]}"
      >
        <span class="initial" aria-hidden="true">{user.username.charAt(0).toUpperCase()}</span>
        {user.username}
      </a>
    </div>
  </div>
</header>

<style>
  header {
    border-bottom: 1px solid var(--line);
    background: var(--surface);
  }

  .inner {
    max-width: 1240px;
    margin: 0 auto;
    padding: 14px 24px;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px 24px;
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: var(--font-head);
    font-weight: 700;
    font-size: 20px;
    letter-spacing: -0.01em;
  }

  .end {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .account {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    min-height: 44px;
    padding: 0 12px 0 8px;
    border-radius: 10px;
    border: 1px solid var(--line);
    font-size: 14px;
    font-weight: 500;
  }

  .scan {
    width: 44px;
    height: 44px;
    box-sizing: border-box;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 10px;
    background: var(--accent);
    color: var(--onaccent);
  }

  .account[aria-current="page"] {
    border-color: var(--text);
  }

  .initial {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: var(--chip);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 13px;
  }
</style>
