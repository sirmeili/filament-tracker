<script lang="ts">
  import { describeError } from "#lib/api/errors.ts";
  import {
    getSettings,
    saveSettings,
    settingProblems,
    testHomeAssistant,
    useEnvValue,
    type SettingOut,
    type TestOut,
  } from "#lib/api/settings.ts";
  import SettingField from "#lib/components/settings/SettingField.svelte";
  import {
    changedValues,
    eventsResultText,
    HOME_ASSISTANT_FIELDS,
    mqttResultText,
    startValue,
  } from "#lib/settings-fields.ts";

  /** The Home Assistant group: the broker for the entities and the address and token for
   * events. Saving applies at once on the server. */
  const GROUP = "home-assistant";

  let settings = $state<SettingOut[] | null>(null);
  let draft = $state<Record<string, string>>({});
  let problems = $state<Record<string, string>>({});
  let failure = $state<string | null>(null);
  let message = $state<string | null>(null);
  let tested = $state<TestOut | null>(null);
  let busy = $state(false);

  const byKey = $derived(new Map((settings ?? []).map((s) => [s.key, s])));
  const changed = $derived(settings ? changedValues(settings, draft) : {});
  const dirty = $derived(Object.keys(changed).length > 0);

  function show(next: SettingOut[]): void {
    settings = next;
    draft = Object.fromEntries(next.map((s) => [s.key, startValue(s)]));
  }

  async function load(): Promise<void> {
    try {
      show((await getSettings(GROUP)).settings);
      failure = null;
    } catch (error) {
      failure = describeError(error);
    }
  }

  $effect(() => {
    void load();
  });

  async function run(action: () => Promise<void>, done: string): Promise<void> {
    busy = true;
    message = null;
    problems = {};
    try {
      await action();
      message = done;
    } catch (error) {
      const byField = settingProblems(error);
      if (byField) problems = byField;
      else message = describeError(error);
    } finally {
      busy = false;
    }
  }

  function save(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    tested = null;
    return run(async () => {
      show((await saveSettings(GROUP, changed)).settings);
    }, "Saved. Home Assistant is using the new settings.");
  }

  function test(): Promise<void> {
    tested = null;
    return run(async () => {
      tested = await testHomeAssistant(changed);
    }, "");
  }

  function clear(key: string): Promise<void> {
    return run(async () => {
      show((await saveSettings(GROUP, {}, [key])).settings);
    }, "Cleared.");
  }

  function reset(key: string): Promise<void> {
    return run(async () => {
      await useEnvValue(GROUP, key);
      show((await getSettings(GROUP)).settings);
    }, "Back to the .env value.");
  }
</script>

<section class="card" aria-labelledby="ha-h">
  <div>
    <h2 id="ha-h" class="label">Home Assistant</h2>
    <p class="muted intro">
      Values from <code>.env</code> are the starting point; a value saved here is used instead. Passwords
      and tokens are stored encrypted and never shown again.
    </p>
  </div>

  {#if failure}
    <p role="alert" class="error">{failure}</p>
  {:else if !settings}
    <p class="muted">Loading…</p>
  {:else}
    <form onsubmit={save} novalidate>
      <div class="fields">
        {#each HOME_ASSISTANT_FIELDS as info (info.key)}
          {@const setting = byKey.get(info.key)}
          {#if setting}
            <SettingField
              {info}
              {setting}
              bind:value={draft[info.key]}
              problem={problems[info.key]}
              {busy}
              onclear={clear}
              onreset={reset}
            />
          {/if}
        {/each}
      </div>
      <div class="buttons">
        <button type="submit" class="primary" disabled={busy || !dirty}>Save</button>
        <button type="button" disabled={busy} onclick={test}>Test</button>
      </div>
      {#if message}<p role="status" class="muted">{message}</p>{/if}
      {#if tested}
        <ul class="results" aria-label="Test results">
          <li class:ok={tested.mqtt === "ok"}>{mqttResultText(tested.mqtt)}</li>
          <li class:ok={tested.events === "ok"}>{eventsResultText(tested.events)}</li>
        </ul>
      {/if}
    </form>
  {/if}
</section>

<style>
  section {
    display: flex;
    flex-direction: column;
    gap: 16px;
    max-width: 760px;
  }

  .intro {
    margin: 6px 0 0;
    font-size: 14px;
  }

  form {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .fields {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 18px 20px;
  }

  .buttons {
    display: flex;
    gap: 10px;
  }

  .results {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 14px;
  }

  .results li {
    padding: 8px 12px;
    border-radius: 10px;
    background: var(--lowbg);
    color: var(--lowtext);
  }

  .results li.ok {
    background: var(--okbg);
    color: var(--oktext);
  }
</style>
