<script lang="ts">
  import { testHomeAssistant } from "#lib/api/settings.ts";
  import SettingsGroupCard, {
    type TestLine,
  } from "#lib/components/settings/SettingsGroupCard.svelte";
  import { eventsResultText, HOME_ASSISTANT_FIELDS, mqttResultText } from "#lib/settings-fields.ts";

  /** The Home Assistant group: the broker for the entities and the address and token for
   * events. Saving reconnects both on the server. */
  async function test(changed: Record<string, string>): Promise<TestLine[]> {
    const result = await testHomeAssistant(changed);
    return [
      { text: mqttResultText(result.mqtt), ok: result.mqtt === "ok" },
      { text: eventsResultText(result.events), ok: result.events === "ok" },
    ];
  }
</script>

<SettingsGroupCard
  group="home-assistant"
  title="Home Assistant"
  intro="Values from .env are the starting point; a value saved here is used instead. Passwords and tokens are stored encrypted and never shown again."
  fields={HOME_ASSISTANT_FIELDS}
  savedText="Saved. Home Assistant is using the new settings."
  {test}
/>
