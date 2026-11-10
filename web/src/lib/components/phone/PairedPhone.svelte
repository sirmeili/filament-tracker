<script lang="ts">
  // A set-up phone on the Pairing page: where it is paired, where it opens, and Unlink.
  import { session } from "#lib/auth/session.svelte.ts";
  import OpensOn from "#lib/components/phone/OpensOn.svelte";
  import { phone } from "#lib/phone/phone-state.svelte.ts";

  interface Props {
    /** After unlinking: whether the token was revoked on the server. */
    onunlinked: (revoked: boolean) => void;
  }

  let { onunlinked }: Props = $props();

  let confirming = $state(false);
  let unlinking = $state(false);

  /** Unlink: sign out (the phone no longer belongs to anyone), then revoke and forget. */
  async function unlink(): Promise<void> {
    confirming = false;
    unlinking = true;
    try {
      await session.logout().catch(() => {});
      onunlinked(await phone.unlink());
    } finally {
      unlinking = false;
    }
  }
</script>

{#if phone.session}
  <p>
    Paired with <span class="mono">{phone.session.pairing.url}</span> as
    <span class="mono">{phone.session.pairing.deviceId}</span>.
  </p>

  <h2 id="opens-h">This phone opens on</h2>
  <OpensOn value={phone.openOn ?? "scan"} onchoose={(value) => phone.chooseOpenOn(value)} />

  {#if phone.queueSize > 0}
    <p class="warn" role="alert">
      {phone.queueSize} queued scans have not been sent yet. Unlinking drops them.
    </p>
  {/if}
  {#if unlinking}
    <p class="muted" role="status">Unlinking…</p>
  {:else if confirming}
    <p id="unlink-what">
      Unlinking signs this phone out and removes the server address, token and tag key constant from
      it. If the server can be reached, it also revokes this phone's token there.
    </p>
    <div class="row" role="group" aria-label="Confirm" aria-describedby="unlink-what">
      <button type="button" class="primary" onclick={unlink}>Unlink this phone</button>
      <button type="button" onclick={() => (confirming = false)}>Cancel</button>
    </div>
  {:else}
    <div class="row">
      <a class="button primary" href="/scan">Scan</a>
      <button type="button" onclick={() => (confirming = true)}>Unlink this phone</button>
    </div>
  {/if}
{/if}

<style>
  p,
  h2 {
    margin: 0;
  }

  h2 {
    font-size: 1rem;
  }

  .row {
    display: flex;
    gap: 10px;
  }

  .warn {
    padding: 12px 14px;
    border-radius: 12px;
    background: var(--lowbg);
    color: var(--lowtext);
  }
</style>
