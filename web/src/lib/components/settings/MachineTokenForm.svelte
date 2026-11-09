<script lang="ts">
  /** Make a machine token: a name and a role. */
  import { describeError } from "#lib/api/errors.ts";
  import { createToken, type MachineTokenCreated } from "#lib/api/tokens.ts";
  import { ROLE_LABELS, ROLES, type Role } from "#lib/roles.ts";

  interface Props {
    oncreated: (token: MachineTokenCreated) => void;
    oncancel: () => void;
  }

  let { oncreated, oncancel }: Props = $props();

  let name = $state("");
  let role = $state<Role>("viewer");
  let problem = $state<string | null>(null);
  let busy = $state(false);

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (!name.trim()) return void (problem = "Enter a name, such as Home Assistant.");
    busy = true;
    problem = null;
    try {
      oncreated(await createToken(name.trim(), role));
    } catch (error) {
      problem = describeError(error);
    } finally {
      busy = false;
    }
  }
</script>

<form onsubmit={submit} aria-label="New machine token" novalidate>
  <div class="row">
    <label class="field">
      Name
      <input
        type="text"
        maxlength="100"
        autocomplete="off"
        placeholder="Home Assistant"
        bind:value={name}
      />
    </label>
    <label class="field">
      Role
      <select bind:value={role}>
        {#each ROLES as option (option)}<option value={option}>{ROLE_LABELS[option]}</option>{/each}
      </select>
    </label>
  </div>
  <p class="muted small">Give it the lowest role that does the job. Viewer can only read.</p>
  {#if problem}<p role="alert" class="error">{problem}</p>{/if}
  <div class="actions">
    <button type="submit" class="primary" disabled={busy}>Make token</button>
    <button type="button" disabled={busy} onclick={oncancel}>Cancel</button>
  </div>
</form>

<style>
  form {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .row {
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 6px;
    flex: 1 1 200px;
    font-size: 13px;
    font-weight: 600;
    color: var(--muted);
  }

  .field input,
  .field select {
    color: var(--text);
  }

  p {
    margin: 0;
  }

  .small {
    font-size: 13px;
  }

  .actions {
    display: flex;
    gap: 10px;
  }
</style>
