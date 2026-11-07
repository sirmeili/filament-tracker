<script lang="ts">
  import type { SettingOut } from "#lib/api/settings.ts";
  import { sourceText, type FieldInfo } from "#lib/settings-fields.ts";

  /** One setting: its box, where its value comes from, and the buttons to clear a secret
   * or go back to the .env value. A secret is never shown: its box starts empty, and
   * leaving it empty keeps the saved one. */
  interface Props {
    info: FieldInfo;
    setting: SettingOut;
    value: string;
    problem?: string | null;
    busy?: boolean;
    onclear: (key: string) => void;
    onreset: (key: string) => void;
  }

  let {
    info,
    setting,
    value = $bindable(),
    problem = null,
    busy = false,
    onclear,
    onreset,
  }: Props = $props();

  const id = $derived(`setting-${setting.key}`);
  const placeholder = $derived(
    setting.secret
      ? setting.set
        ? "Saved. Leave empty to keep it."
        : "Not set"
      : (info.placeholder ?? ""),
  );
</script>

<div class="setting">
  <div class="top">
    <label for={id}>{info.label}</label>
    <span
      class="source"
      class:app={setting.source === "app"}
      class:warn={setting.unreadable}
      data-source={setting.source}>{sourceText(setting)}</span
    >
  </div>
  <input
    {id}
    type={setting.secret ? "password" : "text"}
    autocomplete={setting.secret ? "new-password" : "off"}
    autocapitalize="none"
    spellcheck="false"
    maxlength="1024"
    {placeholder}
    aria-describedby="{id}-help"
    aria-invalid={problem ? "true" : undefined}
    disabled={busy}
    bind:value
  />
  <p id="{id}-help" class="help muted">{info.help}</p>
  {#if problem}<p class="error" role="alert">{info.label}: {problem}</p>{/if}
  {#if (setting.secret && setting.set) || setting.source === "app"}
    <div class="actions">
      {#if setting.secret && setting.set}
        <button
          type="button"
          class="small"
          disabled={busy}
          aria-label="Clear {info.label}"
          onclick={() => onclear(setting.key)}>Clear</button
        >
      {/if}
      {#if setting.source === "app"}
        <button
          type="button"
          class="small"
          disabled={busy}
          aria-label="Use the .env value for {info.label}"
          onclick={() => onreset(setting.key)}
          >{setting.has_env ? "Use the .env value" : "Use the default"}</button
        >
      {/if}
    </div>
  {/if}
</div>

<style>
  .setting {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }

  label {
    font-size: 13px;
    font-weight: 600;
    color: var(--muted);
  }

  .source {
    padding: 2px 8px;
    border-radius: 999px;
    background: var(--chip);
    color: var(--muted);
    font-size: 12px;
    font-weight: 600;
    white-space: nowrap;
  }

  .source.app {
    background: var(--okbg);
    color: var(--oktext);
  }

  .source.warn {
    background: var(--lowbg);
    color: var(--lowtext);
  }

  input {
    color: var(--text);
  }

  .help {
    margin: 0;
    font-size: 13px;
  }

  .error {
    margin: 0;
    font-size: 13px;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
</style>
