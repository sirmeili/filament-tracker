<script lang="ts">
  // The first-start screen's address step (Pairing in docs/SPEC.md): the server to sign in to.
  import { normalizeUrl, serverUrlError } from "#lib/pairing.ts";

  interface Props {
    /** Called with the checked address. */
    onchoose: (url: string) => void | Promise<void>;
  }

  let { onchoose }: Props = $props();

  let url = $state("");
  let error = $state<string | null>(null);

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    error = serverUrlError(url);
    if (!error) await onchoose(normalizeUrl(url));
  }
</script>

<form novalidate onsubmit={submit} aria-label="Choose your server">
  <p>Enter your RollCall server's address, then sign in with your account.</p>
  <label
    >Server address<input
      type="url"
      bind:value={url}
      autocomplete="url"
      placeholder="https://rollcall.example.com"
    /></label
  >
  <button type="submit" class="primary">Continue</button>
  {#if error}<p class="warn" role="alert">{error}</p>{/if}
</form>

<style>
  form {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  p {
    margin: 0;
  }

  label {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .warn {
    padding: 12px 14px;
    border-radius: 12px;
    background: var(--lowbg);
    color: var(--lowtext);
  }
</style>
