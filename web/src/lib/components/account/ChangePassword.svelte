<script lang="ts">
  import { changePassword } from "#lib/api/admin.ts";
  import { ApiError } from "#lib/api/client.ts";
  import { describeError } from "#lib/api/errors.ts";
  import PasswordMeter from "#lib/components/ui/PasswordMeter.svelte";
  import { passwordOk } from "#lib/password.ts";

  let current = $state("");
  let next = $state("");
  let confirm = $state("");
  let problem = $state<string | null>(null);
  let done = $state(false);
  let busy = $state(false);

  function failure(error: unknown): string {
    if (error instanceof ApiError && error.status === 403) return "The current password is wrong.";
    if (error instanceof ApiError && error.status === 429) {
      return "Too many failed attempts. Try again in a few minutes.";
    }
    return describeError(error);
  }

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    done = false;
    if (!current) return void (problem = "Enter your current password.");
    if (!passwordOk(next)) return void (problem = "The new password needs at least 12 characters.");
    if (next !== confirm) return void (problem = "The new passwords do not match.");
    busy = true;
    problem = null;
    try {
      await changePassword(current, next);
      current = next = confirm = "";
      done = true;
    } catch (error) {
      problem = failure(error);
    } finally {
      busy = false;
    }
  }
</script>

<form class="card" onsubmit={submit} aria-labelledby="pw-h" novalidate>
  <h2 id="pw-h" class="label">Change password</h2>
  <label class="field">
    Current password
    <input type="password" autocomplete="current-password" maxlength="256" bind:value={current} />
  </label>
  <label class="field">
    New password
    <input type="password" autocomplete="new-password" maxlength="256" bind:value={next} />
  </label>
  <PasswordMeter password={next} />
  <label class="field">
    Confirm new password
    <input type="password" autocomplete="new-password" maxlength="256" bind:value={confirm} />
  </label>
  <p class="muted hint">At least 12 characters. Changing it signs you out everywhere else.</p>
  {#if problem}<p role="alert" class="error">{problem}</p>{/if}
  {#if done}<p role="status">Password changed. Your other sessions have been signed out.</p>{/if}
  <button type="submit" class="primary" disabled={busy}>Change password</button>
</form>

<style>
  form {
    max-width: 560px;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 13px;
    font-weight: 600;
    color: var(--muted);
  }

  .field input {
    color: var(--text);
  }

  p {
    margin: 0;
    font-size: 14px;
  }

  .hint {
    font-size: 13px;
  }

  button {
    align-self: flex-start;
  }
</style>
