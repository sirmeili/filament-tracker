<script lang="ts">
  import { goto } from "$app/navigation";
  import { session } from "#lib/auth/session.svelte.ts";
  import OpensOn from "#lib/components/phone/OpensOn.svelte";
  import PairedPhone from "#lib/components/phone/PairedPhone.svelte";
  import PairWithCode from "#lib/components/phone/PairWithCode.svelte";
  import ServerAddress from "#lib/components/phone/ServerAddress.svelte";
  import SetUpPhone from "#lib/components/phone/SetUpPhone.svelte";
  import type { OpenOn } from "#lib/phone/pairing-store.ts";
  import { phone } from "#lib/phone/phone-state.svelte.ts";

  /** What the last unlink did: the token was revoked, or the device is still listed. */
  let unlinked = $state<"revoked" | "listed" | null>(null);
  /** First start: pair with a code instead of signing in. */
  let byCode = $state(false);
  /** Just set up by signing in: ask where the phone opens. */
  let welcome = $state(false);

  async function chooseServer(url: string): Promise<void> {
    unlinked = null;
    await phone.chooseServer(url);
    await goto("/login");
  }

  /** Back to the address step: sign out of the old server first. */
  async function changeServer(): Promise<void> {
    await session.logout().catch(() => {});
    await phone.chooseServer(null);
    session.loaded = false;
  }

  /** Set up by signing in. Welcome is set first, so the page goes straight from setting up
   * to the opening-screen question, without showing the set-up phone in between. */
  async function setUp(): Promise<void> {
    welcome = true;
    try {
      await phone.setUp();
    } catch (error) {
      welcome = false;
      throw error;
    }
  }

  async function opensOn(value: OpenOn): Promise<void> {
    await phone.chooseOpenOn(value);
    await goto(value === "scan" ? "/scan" : "/");
  }
</script>

<svelte:head><title>Pairing · RollCall</title></svelte:head>

<section class="pair" aria-labelledby="pair-h">
  {#if !phone.app}
    <h1 id="pair-h">Pairing</h1>
    <p class="muted">Pairing is for the RollCall Android app.</p>
  {:else if phone.session && welcome}
    <h1 id="pair-h">This phone is set up</h1>
    <p>What will you mainly use it for? You can change this later on this page.</p>
    <OpensOn value={null} onchoose={opensOn} />
  {:else if phone.session}
    <h1 id="pair-h">Pairing</h1>
    <PairedPhone onunlinked={(revoked) => (unlinked = revoked ? "revoked" : "listed")} />
  {:else}
    <h1 id="pair-h">Set up this phone</h1>
    {#if unlinked === "revoked"}
      <p role="status">This phone is unlinked, and its token was revoked on the server.</p>
    {:else if unlinked === "listed"}
      <p class="warn" role="alert">
        This phone is unlinked, but the server could not be reached, so its token still works there.
        An Admin should revoke this phone on the Devices page.
      </p>
    {/if}
    {#if phone.server}
      <SetUpPhone
        server={phone.server}
        user={session.user}
        loaded={session.loaded}
        {setUp}
        onchangeserver={changeServer}
      />
    {:else if byCode}
      <PairWithCode />
      <button type="button" class="small" onclick={() => (byCode = false)}>Sign in instead</button>
    {:else}
      <ServerAddress onchoose={chooseServer} />
      <button type="button" class="small" onclick={() => (byCode = true)}
        >Pair with a code instead</button
      >
    {/if}
  {/if}
</section>

<style>
  .pair {
    display: flex;
    flex-direction: column;
    gap: 16px;
    max-width: 560px;
    margin: 0 auto;
  }

  h1 {
    margin: 0;
  }

  p {
    margin: 0;
  }

  .small {
    align-self: flex-start;
  }

  .warn {
    padding: 12px 14px;
    border-radius: 12px;
    background: var(--lowbg);
    color: var(--lowtext);
  }
</style>
