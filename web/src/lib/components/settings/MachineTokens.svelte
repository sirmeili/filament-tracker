<script lang="ts">
  /** The Machine tokens card: tokens for Home Assistant and scripts, each shown once. */
  import { describeError } from "#lib/api/errors.ts";
  import {
    listTokens,
    madeText,
    revokeToken,
    usedText,
    type MachineTokenCreated,
    type MachineTokenOut,
  } from "#lib/api/tokens.ts";
  import MachineTokenForm from "#lib/components/settings/MachineTokenForm.svelte";
  import { ROLE_LABELS } from "#lib/roles.ts";

  let tokens = $state<MachineTokenOut[] | null>(null);
  let failure = $state<string | null>(null);
  let message = $state<string | null>(null);
  let making = $state(false);
  let shown = $state<MachineTokenCreated | null>(null);
  let confirming = $state<number | null>(null);
  let copied = $state<string | null>(null);
  let busy = $state(false);

  async function load(): Promise<void> {
    try {
      tokens = await listTokens();
      failure = null;
    } catch (error) {
      failure = describeError(error);
    }
  }

  $effect(() => {
    void load();
  });

  async function created(token: MachineTokenCreated): Promise<void> {
    making = false;
    message = null;
    copied = null;
    shown = token;
    await load();
  }

  async function revoke(token: MachineTokenOut): Promise<void> {
    confirming = null;
    busy = true;
    try {
      await revokeToken(token.id);
      message = `Revoked ${token.name}. It is refused from now on.`;
    } catch (error) {
      message = describeError(error);
    } finally {
      await load();
      busy = false;
    }
  }

  async function copy(token: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(token);
      copied = "Copied.";
    } catch {
      copied = "Could not copy. Select the token and copy it by hand.";
    }
  }
</script>

<section class="card" aria-labelledby="tokens-h">
  <div class="head">
    <h2 id="tokens-h" class="label">Machine tokens</h2>
    {#if !making && !shown}
      <button type="button" onclick={() => (making = true)}>New token</button>
    {/if}
  </div>
  <p class="muted small">
    For Home Assistant and scripts. Each token acts with its role and works only from your LAN. Send
    it in the <code>Authorization: Bearer</code> header.
  </p>

  {#if making}
    <MachineTokenForm oncreated={created} oncancel={() => (making = false)} />
  {/if}

  {#if shown}
    <div class="shown" role="alert" aria-label="New token for {shown.name}">
      <strong>Copy the token for {shown.name} now. It won't be shown again.</strong>
      <div class="row">
        <code class="token">{shown.token}</code>
        <button type="button" onclick={() => copy(shown!.token)}>Copy</button>
        <button type="button" class="primary" onclick={() => (shown = null)}>Done</button>
      </div>
      {#if copied}<span class="small">{copied}</span>{/if}
    </div>
  {/if}

  {#if message}<p role="status" class="muted">{message}</p>{/if}

  {#if failure}
    <p role="alert" class="error">{failure}</p>
  {:else if !tokens}
    <p class="muted">Loading…</p>
  {:else if tokens.length === 0}
    <p class="muted">No machine tokens yet.</p>
  {:else}
    <ul aria-label="Machine tokens">
      {#each tokens as token (token.id)}
        <li class:revoked={token.revoked}>
          <div class="info">
            <strong>{token.name}</strong>
            <span class="pill">{ROLE_LABELS[token.role]}</span>
            {#if token.revoked}<span class="pill">Revoked</span>{/if}
            <span class="muted small">{madeText(token)} · {usedText(token)}</span>
          </div>
          {#if !token.revoked}
            {#if confirming === token.id}
              <div class="actions" role="group" aria-label="Confirm">
                <span class="small">Anything using it stops working.</span>
                <button type="button" class="primary" disabled={busy} onclick={() => revoke(token)}
                  >Revoke {token.name}</button
                >
                <button type="button" onclick={() => (confirming = null)}>Cancel</button>
              </div>
            {:else}
              <button type="button" disabled={busy} onclick={() => (confirming = token.id)}
                >Revoke</button
              >
            {/if}
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .card {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }

  p {
    margin: 0;
  }

  .small {
    font-size: 13px;
  }

  code {
    font-family: var(--font-mono);
  }

  .shown {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 16px 20px;
    border-radius: 16px;
    background: var(--lowbg);
    color: var(--lowtext);
  }

  .row,
  .actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
  }

  .token {
    flex: 1 1 280px;
    font-size: 14px;
    padding: 10px 12px;
    border-radius: 10px;
    background: var(--surface);
    color: var(--text);
    word-break: break-all;
    user-select: all;
  }

  ul {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
  }

  li {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 12px 0;
    border-top: 1px solid var(--line);
  }

  li.revoked {
    opacity: 0.6;
  }

  .info {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 8px;
  }

  .pill {
    font-size: 12px;
    padding: 2px 8px;
    border-radius: 999px;
    background: var(--chip);
  }
</style>
