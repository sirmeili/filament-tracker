<script lang="ts" module>
  export interface TestLine {
    text: string;
    ok: boolean;
  }
</script>

<script lang="ts">
  import { describeError } from "#lib/api/errors.ts";
  import {
    getSettings,
    saveSettings,
    settingProblems,
    useEnvValue,
    type SettingOut,
    type SettingsGroup,
  } from "#lib/api/settings.ts";
  import SettingField from "#lib/components/settings/SettingField.svelte";
  import { changedValues, startValue, type FieldInfo } from "#lib/settings-fields.ts";

  /** One settings group on the Settings page: its fields, Save, and an optional Test.
   * Saving applies at once on the server. */
  interface Props {
    group: SettingsGroup;
    title: string;
    intro: string;
    fields: readonly FieldInfo[];
    savedText: string;
    /** Try the changed values without saving; one line per result. */
    test?: (changed: Record<string, string>) => Promise<TestLine[]>;
    /** Called with the settings as saved. */
    onsaved?: (settings: SettingOut[]) => void;
  }

  let { group, title, intro, fields, savedText, test, onsaved }: Props = $props();

  let settings = $state<SettingOut[] | null>(null);
  let draft = $state<Record<string, string>>({});
  let problems = $state<Record<string, string>>({});
  let failure = $state<string | null>(null);
  let message = $state<string | null>(null);
  let tested = $state<TestLine[] | null>(null);
  let busy = $state(false);

  const headingId = $derived(`${group}-h`);
  const byKey = $derived(new Map((settings ?? []).map((s) => [s.key, s])));
  const changed = $derived(settings ? changedValues(settings, draft) : {});
  const dirty = $derived(Object.keys(changed).length > 0);

  function show(next: SettingOut[]): void {
    settings = next;
    draft = Object.fromEntries(next.map((s) => [s.key, startValue(s)]));
  }

  async function load(): Promise<void> {
    try {
      show((await getSettings(group)).settings);
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

  function saved(next: SettingOut[]): void {
    show(next);
    onsaved?.(next);
  }

  function save(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    tested = null;
    return run(async () => {
      saved((await saveSettings(group, changed)).settings);
    }, savedText);
  }

  function runTest(): Promise<void> {
    tested = null;
    return run(async () => {
      if (test) tested = await test(changed);
    }, "");
  }

  function clear(key: string): Promise<void> {
    return run(async () => {
      saved((await saveSettings(group, {}, [key])).settings);
    }, "Cleared.");
  }

  function reset(key: string): Promise<void> {
    return run(async () => {
      await useEnvValue(group, key);
      saved((await getSettings(group)).settings);
    }, "Back to the .env value.");
  }
</script>

<section class="card" aria-labelledby={headingId}>
  <div>
    <h2 id={headingId} class="label">{title}</h2>
    <p class="muted intro">{intro}</p>
  </div>

  {#if failure}
    <p role="alert" class="error">{failure}</p>
  {:else if !settings}
    <p class="muted">Loading…</p>
  {:else}
    <form onsubmit={save} novalidate aria-label={title}>
      <div class="fields">
        {#each fields as info (info.key)}
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
        {#if test}<button type="button" disabled={busy} onclick={runTest}>Test</button>{/if}
      </div>
      {#if message}<p role="status" class="muted">{message}</p>{/if}
      {#if tested}
        <ul class="results" aria-label="Test results">
          {#each tested as line (line.text)}
            <li class:ok={line.ok}>{line.text}</li>
          {/each}
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
