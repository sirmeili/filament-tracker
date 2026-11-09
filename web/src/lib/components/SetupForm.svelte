<script lang="ts">
  /** First-start setup: the setup code from the server's log, the first Admin, and the
   * starter settings the server does not have yet. */
  import { ApiError } from "#lib/api/client.ts";
  import { settingProblems } from "#lib/api/settings.ts";
  import type { SetupFields, SetupStatus } from "#lib/api/setup.ts";
  import PasswordMeter from "#lib/components/ui/PasswordMeter.svelte";
  import { passwordOk } from "#lib/password.ts";
  import { timeZoneNames } from "#lib/settings-fields.ts";

  interface Props {
    status: SetupStatus;
    onsubmit: (fields: SetupFields) => Promise<unknown>;
  }

  let { status, onsubmit }: Props = $props();

  let code = $state("");
  let username = $state("");
  let password = $state("");
  let timeZone = $state(Intl.DateTimeFormat().resolvedOptions().timeZone ?? "");
  let salt = $state("");
  let busy = $state(false);
  let error = $state<string | null>(null);
  let problems = $state<Record<string, string>>({});

  const zones = timeZoneNames();

  function messageFor(failure: unknown): string {
    if (failure instanceof ApiError) {
      if (failure.status === 403) return "That setup code is wrong. Check the server's log.";
      if (failure.status === 429) return "Too many wrong codes. Try again in a few minutes.";
      if (failure.status === 409) return "Setup is already done. Sign in instead.";
      if (failure.status === 422) return "Check the fields marked below.";
      return failure.message;
    }
    return "Something went wrong. Try again.";
  }

  function localProblems(): Record<string, string> {
    const found: Record<string, string> = {};
    if (!code.trim()) found.code = "Enter the setup code from the server's log.";
    if (!username.trim()) found.username = "Choose a username.";
    if (!passwordOk(password)) found.password = "The password needs at least 12 characters.";
    return found;
  }

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    error = null;
    problems = localProblems();
    if (Object.keys(problems).length) return;
    const fields: SetupFields = {
      code: code.trim(),
      username: username.trim().toLowerCase(),
      password,
    };
    if (status.time_zone_needed && timeZone.trim()) fields.time_zone = timeZone.trim();
    if (status.kdf_salt_needed && salt.trim()) fields.kdf_salt = salt.trim();
    busy = true;
    try {
      await onsubmit(fields);
    } catch (failure) {
      error = messageFor(failure);
      problems = settingProblems(failure) ?? {};
    } finally {
      busy = false;
    }
  }
</script>

{#snippet problem(field: string)}
  {#if problems[field]}<span class="problem" id="setup-{field}-problem">{problems[field]}</span
    >{/if}
{/snippet}

<form onsubmit={submit} aria-labelledby="setup-title" novalidate>
  <h1 id="setup-title">Set up Filament Tracker</h1>
  <p class="muted">
    No one can sign in yet. Create the first Admin account. The setup code is in the server's log; a
    new one is made each time the server starts.
  </p>
  {#if error}<p class="error" role="alert">{error}</p>{/if}

  <label>
    Setup code
    <input
      class="mono"
      autocomplete="off"
      autocapitalize="characters"
      spellcheck="false"
      placeholder="XXXX-XXXX-XXXX"
      maxlength="64"
      aria-invalid={problems.code ? "true" : undefined}
      aria-describedby={problems.code ? "setup-code-problem" : undefined}
      bind:value={code}
    />
  </label>
  {@render problem("code")}

  <fieldset>
    <legend>First Admin</legend>
    <label>
      Username
      <input
        autocomplete="username"
        autocapitalize="none"
        spellcheck="false"
        maxlength="32"
        aria-invalid={problems.username ? "true" : undefined}
        aria-describedby={problems.username ? "setup-username-problem" : undefined}
        bind:value={username}
      />
    </label>
    {@render problem("username")}
    <label>
      Password
      <input
        type="password"
        autocomplete="new-password"
        maxlength="256"
        aria-invalid={problems.password ? "true" : undefined}
        aria-describedby={problems.password ? "setup-password-problem" : undefined}
        bind:value={password}
      />
    </label>
    {@render problem("password")}
    <PasswordMeter {password} />
  </fieldset>

  {#if status.time_zone_needed || status.kdf_salt_needed}
    <fieldset>
      <legend>Starter settings (optional)</legend>
      {#if status.time_zone_needed}
        <label>
          Time zone
          <input
            list="setup-zones"
            autocomplete="off"
            spellcheck="false"
            maxlength="64"
            aria-invalid={problems.time_zone ? "true" : undefined}
            aria-describedby={problems.time_zone ? "setup-time_zone-problem" : undefined}
            bind:value={timeZone}
          />
          <datalist id="setup-zones">
            {#each zones as zone (zone)}<option value={zone}></option>{/each}
          </datalist>
        </label>
        {@render problem("time_zone")}
      {/if}
      {#if status.kdf_salt_needed}
        <label>
          Key-derivation salt
          <input
            type="password"
            class="mono"
            autocomplete="off"
            spellcheck="false"
            maxlength="128"
            aria-invalid={problems.kdf_salt ? "true" : undefined}
            aria-describedby={problems.kdf_salt ? "setup-kdf_salt-problem" : undefined}
            bind:value={salt}
          />
        </label>
        {@render problem("kdf_salt")}
      {/if}
      <p class="muted small">Both can be set or changed later on the Settings page.</p>
    </fieldset>
  {/if}

  <button type="submit" class="primary" disabled={busy}>
    {busy ? "Setting up…" : "Create Admin and sign in"}
  </button>
</form>

<style>
  form {
    display: grid;
    gap: 1rem;
    width: min(100%, 30rem);
    padding: 28px;
    border: 1px solid var(--line);
    border-radius: 16px;
    background: var(--surface);
  }

  h1 {
    margin: 0;
    font-size: 28px;
  }

  p {
    margin: 0;
  }

  fieldset {
    display: grid;
    gap: 1rem;
    margin: 0;
    padding: 0;
    border: 0;
  }

  legend {
    padding: 0 0 0.5rem;
    font-weight: 700;
  }

  label {
    display: grid;
    gap: 0.3rem;
    font-weight: 600;
  }

  .mono {
    font-family: var(--font-mono);
  }

  .problem {
    /* Close to its field, inside the form's gap. */
    margin-top: -0.6rem;
    color: var(--danger);
    font-size: 13px;
    font-weight: 400;
  }

  .small {
    font-size: 13px;
  }
</style>
