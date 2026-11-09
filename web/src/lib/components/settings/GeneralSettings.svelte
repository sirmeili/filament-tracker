<script lang="ts">
  import type { SettingOut } from "#lib/api/settings.ts";
  import { session } from "#lib/auth/session.svelte.ts";
  import SettingsGroupCard from "#lib/components/settings/SettingsGroupCard.svelte";
  import { GENERAL_FIELDS } from "#lib/settings-fields.ts";

  /** The time zone every time is shown in, and how long a sign-in lasts. A saved time zone
   * applies to this browser at once. */
  function saved(settings: SettingOut[]): void {
    const zone = settings.find((s) => s.key === "tz")?.value;
    if (zone && session.user) session.user = { ...session.user, time_zone: zone };
  }
</script>

<SettingsGroupCard
  group="general"
  title="General"
  intro="The time zone sets every time the web app shows, for everyone, and when the nightly backup runs. A new sign-in length applies from the next sign-in."
  fields={GENERAL_FIELDS}
  savedText="Saved."
  onsaved={saved}
/>
