<script lang="ts">
  import type { UserOut } from "#lib/api/types.ts";
  import { dateTime } from "#lib/format.ts";
  import { passwordOk } from "#lib/password.ts";
  import { ROLE_LABELS, ROLES, type Role } from "#lib/roles.ts";

  interface Props {
    user: UserOut;
    /** The signed-in admin's own row: no changes, so nobody locks themselves out. */
    you: boolean;
    busy: boolean;
    onchange: (
      user: UserOut,
      changes: { role?: Role; disabled?: boolean; password?: string },
      done: string,
    ) => void;
  }

  let { user, you, busy, onchange }: Props = $props();

  let resetting = $state(false);
  let password = $state("");

  function reset(event: SubmitEvent): void {
    event.preventDefault();
    if (!passwordOk(password)) return;
    onchange(user, { password }, `Reset the password for ${user.username}.`);
    resetting = false;
    password = "";
  }
</script>

<tr class:off={user.disabled}>
  <td>
    <div class="who">
      <span class="av" aria-hidden="true">{user.username.charAt(0).toUpperCase()}</span>
      <span class="name">{user.username}</span>
      {#if you}<span class="pill">You</span>{/if}
      {#if user.disabled}<span class="pill dis">Disabled</span>{/if}
    </div>
  </td>
  <td>
    <label>
      <span class="sr-only">Role for {user.username}</span>
      <select
        value={user.role}
        disabled={you || busy}
        onchange={(e) => {
          const role = e.currentTarget.value as Role;
          onchange(user, { role }, `${user.username} is now ${ROLE_LABELS[role]}.`);
        }}
      >
        {#each ROLES as option (option)}<option value={option}>{ROLE_LABELS[option]}</option>{/each}
      </select>
    </label>
  </td>
  <td class="date">{user.last_login_at ? dateTime(user.last_login_at) : "Never"}</td>
  <td>
    {#if !you}
      {#if resetting}
        <form class="reset" onsubmit={reset}>
          <label>
            <span class="sr-only">New password for {user.username}</span>
            <input
              type="password"
              autocomplete="new-password"
              placeholder="New password, 12+ characters"
              maxlength="256"
              bind:value={password}
            />
          </label>
          <button type="submit" class="small primary" disabled={busy || !passwordOk(password)}
            >Set</button
          >
          <button type="button" class="small" onclick={() => (resetting = false)}>Cancel</button>
        </form>
      {:else}
        <div class="actions">
          <button type="button" class="small" disabled={busy} onclick={() => (resetting = true)}
            >Reset password</button
          >
          {#if user.disabled}
            <button
              type="button"
              class="small"
              disabled={busy}
              onclick={() => onchange(user, { disabled: false }, `Enabled ${user.username}.`)}
              >Enable</button
            >
          {:else}
            <button
              type="button"
              class="small danger"
              disabled={busy}
              onclick={() =>
                onchange(
                  user,
                  { disabled: true },
                  `Disabled ${user.username} and signed them out.`,
                )}>Disable</button
            >
          {/if}
        </div>
      {/if}
    {/if}
  </td>
</tr>

<style>
  .who {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
  }

  .av {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: var(--chip);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 14px;
  }

  .name {
    font-weight: 600;
    font-size: 15px;
  }

  .pill {
    font-size: 11px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 999px;
    background: var(--chip);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .pill.dis {
    background: var(--lowbg);
    color: var(--lowtext);
  }

  tr.off .name {
    color: var(--muted);
  }

  select {
    min-width: 120px;
  }

  .date {
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--muted);
    white-space: nowrap;
  }

  .actions,
  .reset {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }

  .reset input {
    min-width: 220px;
  }
</style>
