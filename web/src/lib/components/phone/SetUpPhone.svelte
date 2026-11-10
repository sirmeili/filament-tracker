<script lang="ts">
  // Setting up by signing in (Pairing in docs/SPEC.md): with a server chosen, sign in, then
  // the phone sets itself up as the user's own phone. Away from home it waits for home.
  import type { Me } from "#lib/api/types.ts";
  import { setUpError } from "#lib/phone/own-phone.ts";

  interface Props {
    server: string;
    /** The signed-in user; null when signed out. */
    user: Me | null;
    /** Whether the sign-in check has finished. */
    loaded: boolean;
    /** Set the phone up; throws when it cannot. */
    setUp: () => Promise<void>;
    /** Go back to the address step. */
    onchangeserver: () => void | Promise<void>;
  }

  let { server, user, loaded, setUp, onchangeserver }: Props = $props();

  let busy = $state(false);
  let failure = $state<{ away: boolean; text: string } | null>(null);
  let tried = false;

  async function run(): Promise<void> {
    busy = true;
    failure = null;
    try {
      await setUp();
    } catch (error) {
      failure = setUpError(error);
    } finally {
      busy = false;
    }
  }

  // Signed in: set the phone up at once, one time; Try again repeats it.
  $effect(() => {
    if (user && !tried) {
      tried = true;
      void run();
    }
  });
</script>

<p>Server: <span class="mono">{server}</span></p>

{#if !loaded}
  <p class="muted" role="status">Checking with the server…</p>
{:else if !user}
  <p>Sign in with your RollCall account to set up this phone.</p>
  <a class="button primary" href="/login">Sign in</a>
{:else if busy}
  <p class="muted" role="status">Setting up this phone for {user.username}…</p>
{:else if failure}
  <p class="warn" role="alert">{failure.text}</p>
  <button type="button" class="primary" onclick={run}>Try again</button>
{/if}

<button type="button" class="small" onclick={onchangeserver}>Use a different server</button>

<style>
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
