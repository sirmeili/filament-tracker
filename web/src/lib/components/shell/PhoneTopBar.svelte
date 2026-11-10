<script lang="ts">
  // The phone layout's top bar: the RollCall mark and the page title, nothing else.
  import RollCallMark from "#lib/components/shell/RollCallMark.svelte";

  let { title }: { title: string } = $props();
</script>

<header class="top">
  <a class="home" href="/" aria-label="RollCall, Inventory"><RollCallMark /></a>
  <!-- The page's own heading stays for screen readers; this is its visible stand-in. -->
  <p class="title" aria-hidden="true">{title}</p>
</header>

<style>
  .top {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 18px 20px 6px;
    padding-top: calc(18px + env(safe-area-inset-top, 0px));
  }

  .home {
    display: inline-flex;
  }

  .title {
    margin: 0;
    font-family: var(--font-head);
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.02em;
  }
</style>
