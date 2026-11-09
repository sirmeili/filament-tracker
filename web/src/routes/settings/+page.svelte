<script lang="ts">
  import GeneralSettings from "#lib/components/settings/GeneralSettings.svelte";
  import HomeAssistantSettings from "#lib/components/settings/HomeAssistantSettings.svelte";
  import ScannerSettings from "#lib/components/settings/ScannerSettings.svelte";
</script>

<svelte:head><title>Settings · Filament Tracker</title></svelte:head>

<div class="page">
  <div class="pagehead">
    <div>
      <h1>Settings</h1>
      <p>Changes apply at once, without restarting the server. Admins only.</p>
    </div>
  </div>

  <GeneralSettings />
  <ScannerSettings />
  <HomeAssistantSettings />
</div>
