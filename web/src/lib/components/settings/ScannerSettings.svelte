<script lang="ts">
  import SettingsGroupCard from "#lib/components/settings/SettingsGroupCard.svelte";
  import { SCANNER_FIELDS } from "#lib/settings-fields.ts";
</script>

<SettingsGroupCard
  group="scanners"
  title="Scanners"
  intro="The key-derivation salt is given to registered scanners and paired phones so they can read tags. The Cloudflare Access service token is given to paired phones so the app works away from home. Both are handed out only on your home network; the salt and the client secret are stored encrypted and never shown again."
  fields={SCANNER_FIELDS}
  savedText="Saved. Scanners and phones get the new values the next time they ask for them; phones ask when the app opens at home."
/>
