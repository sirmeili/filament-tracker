<script lang="ts">
  import { createUser } from "#lib/api/admin.ts";
  import { describeError } from "#lib/api/errors.ts";
  import type { UserOut } from "#lib/api/types.ts";
  import PasswordMeter from "#lib/components/ui/PasswordMeter.svelte";
  import { passwordOk } from "#lib/password.ts";
  import { ROLE_LABELS, ROLES, type Role } from "#lib/roles.ts";

  interface Props {
    oncreated: (user: UserOut) => void;
    oncancel: () => void;
  }

  let { oncreated, oncancel }: Props = $props();

  let username = $state("");
  let role = $state<Role>("viewer");
  let password = $state("");
  let problem = $state<string | null>(null);
  let busy = $state(false);

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (!username.trim()) return void (problem = "Enter a username.");
    if (!passwordOk(password)) return void (problem = "The password needs at least 12 characters.");
    busy = true;
    problem = null;
    try {
      oncreated(await createUser(username.trim().toLowerCase(), role, password));
    } catch (error) {
      problem = describeError(error);
    } finally {
      busy = false;
    }
  }
</script>

<form class="card" onsubmit={submit} aria-labelledby="new-h" novalidate>
  <h2 id="new-h" class="label">New user</h2>
  <div class="row">
    <label class="field">
      Username
      <input
        type="text"
        maxlength="32"
        autocomplete="off"
        autocapitalize="none"
        spellcheck="false"
        bind:value={username}
      />
    </label>
    <label class="field">
      Role
      <select bind:value={role}>
        {#each ROLES as option (option)}<option value={option}>{ROLE_LABELS[option]}</option>{/each}
      </select>
    </label>
  </div>
  <label class="field">
    First password
    <input type="password" autocomplete="new-password" maxlength="256" bind:value={password} />
  </label>
  <PasswordMeter {password} />
  <p class="muted hint">They can change it from their account page.</p>
  {#if problem}<p role="alert" class="error">{problem}</p>{/if}
  <div class="actions">
    <button type="submit" class="primary" disabled={busy}>Create</button>
    <button type="button" onclick={oncancel}>Cancel</button>
  </div>
</form>

<style>
  form {
    max-width: 720px;
  }

  .row {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 6px;
    flex: 1 1 220px;
    font-size: 13px;
    font-weight: 600;
    color: var(--muted);
  }

  .field input,
  .field select {
    color: var(--text);
  }

  .hint {
    margin: 0;
    font-size: 13px;
  }

  .actions {
    display: flex;
    gap: 10px;
  }
</style>
