<script lang="ts">
  import type { Me } from "#lib/api/types.ts";
  import Nav from "#lib/components/Nav.svelte";
  import ThemeControl from "#lib/components/ThemeControl.svelte";
  import { ACCOUNT_PATH, navItemFor, visibleNav } from "#lib/nav.ts";
  import { ROLE_LABELS } from "#lib/roles.ts";
  import type { Theme } from "#lib/theme.svelte.ts";

  interface Props {
    user: Me;
    pathname: string;
    theme: Theme;
    reviewCount: number;
  }

  let { user, pathname, theme, reviewCount }: Props = $props();
</script>

<header>
  <div class="inner">
    <a class="brand" href="/">
      <svg
        width="28"
        height="28"
        viewBox="0 0 28 28"
        fill="none"
        stroke="currentColor"
        stroke-width="2.2"
        aria-hidden="true"
      >
        <circle cx="14" cy="14" r="11"></circle>
        <circle cx="14" cy="14" r="4"></circle>
        <path d="M14 3v4M14 21v4M3 14h4M21 14h4"></path>
      </svg>
      Filament Tracker
    </a>
    <Nav
      items={visibleNav(user.role)}
      current={navItemFor(pathname)}
      badges={{ "/review": reviewCount }}
    />
    <div class="end">
      <ThemeControl {theme} />
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
