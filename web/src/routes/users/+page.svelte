<script lang="ts">
  import { listUsers, updateUser } from "#lib/api/admin.ts";
  import { describeError } from "#lib/api/errors.ts";
  import type { UserOut } from "#lib/api/types.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import NewUserForm from "#lib/components/users/NewUserForm.svelte";
  import UserRow from "#lib/components/users/UserRow.svelte";
  import { ROLE_DESCRIPTIONS, ROLE_LABELS, ROLES, type Role } from "#lib/roles.ts";

  let users = $state<UserOut[] | null>(null);
  let failure = $state<string | null>(null);
  let message = $state<string | null>(null);
  let creating = $state(false);
  let busy = $state(false);

  async function load(): Promise<void> {
    try {
      users = await listUsers();
      failure = null;
    } catch (error) {
      failure = describeError(error);
    }
  }

  $effect(() => {
    void load();
  });

  async function change(
    user: UserOut,
    changes: { role?: Role; disabled?: boolean; password?: string },
    done: string,
  ): Promise<void> {
    busy = true;
    message = null;
    try {
      await updateUser(user.id, changes);
      message = done;
    } catch (error) {
      message = describeError(error);
    } finally {
      // Reload either way, so a refused role change shows the saved role again.
      await load();
      busy = false;
    }
  }

  async function created(user: UserOut): Promise<void> {
    creating = false;
    message = `Created ${user.username} (${ROLE_LABELS[user.role]}).`;
    await load();
  }
</script>

<svelte:head><title>Users · Filament Tracker</title></svelte:head>

<div class="page">
  <div class="pagehead">
    <div>
      <h1>Users</h1>
      <p>There's no sign-up: accounts are created here. Admins only.</p>
    </div>
    {#if !creating}
      <button type="button" class="primary" onclick={() => (creating = true)}>Create user</button>
    {/if}
  </div>

  {#if creating}
    <NewUserForm oncreated={created} oncancel={() => (creating = false)} />
  {/if}
  {#if message}<p role="status" class="muted">{message}</p>{/if}

  {#if failure}
    <p role="alert" class="error">{failure}</p>
  {:else if !users}
    <p class="muted">Loading…</p>
  {:else}
    <div class="tablebox">
      <table>
        <thead>
          <tr>
            <th scope="col">User</th>
            <th scope="col">Role</th>
            <th scope="col">Last sign-in</th>
            <th scope="col"><span class="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          {#each users as user (user.id)}
            <UserRow {user} you={user.id === session.user?.id} {busy} onchange={change} />
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

  <ul class="roles" aria-label="What each role can do">
    {#each ROLES as role (role)}
      <li><strong>{ROLE_LABELS[role]}</strong> {ROLE_DESCRIPTIONS[role]}</li>
    {/each}
  </ul>
</div>

<style>
  table {
    min-width: 760px;
  }

  .roles {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 14px;
    color: var(--muted);
  }

  .roles strong {
    color: var(--text);
  }
</style>
