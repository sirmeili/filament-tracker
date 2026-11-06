<script lang="ts">
  /** A new device token, shown once with a Copy button. */
  interface Props {
    name: string;
    token: string;
    ondone: () => void;
  }

  let { name, token, ondone }: Props = $props();
  let copied = $state<string | null>(null);

  async function copy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(token);
      copied = "Copied.";
    } catch {
      copied = "Could not copy. Select the token and copy it by hand.";
    }
  }
</script>

<section class="panel" role="alert" aria-label="New token for {name}">
  <strong>Copy the token for {name} now. It won't be shown again.</strong>
  <div class="row">
    <code>{token}</code>
    <button type="button" onclick={copy}>Copy</button>
    <button type="button" class="primary" onclick={ondone}>Done</button>
  </div>
  {#if copied}<span>{copied}</span>{/if}
  <span class="muted">
    Enter it in the scanner's setup screen. Scanner routes accept it only from your LAN.
  </span>
</section>

<style>
  .panel {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 16px 20px;
    border-radius: 16px;
    background: var(--lowbg);
    color: var(--lowtext);
  }

  .row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
  }

  code {
    flex: 1 1 280px;
    font-family: var(--font-mono);
    font-size: 14px;
    padding: 10px 12px;
    border-radius: 10px;
    background: var(--surface);
    color: var(--text);
    word-break: break-all;
    user-select: all;
  }

  .muted {
    color: inherit;
    font-size: 13px;
  }
</style>
