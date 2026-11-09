<script lang="ts">
  import SettingsGroupCard from "#lib/components/settings/SettingsGroupCard.svelte";
  import { SCANNER_FIELDS } from "#lib/settings-fields.ts";
</script>

<SettingsGroupCard
  group="scanners"
  title="Scanners"
  intro="The key-derivation salt is given to registered scanners and paired phones so they can read tags. It is stored encrypted and never shown again."
  fields={SCANNER_FIELDS}
  savedText="Saved. Scanners and phones get the new salt the next time they ask for it."
/>
