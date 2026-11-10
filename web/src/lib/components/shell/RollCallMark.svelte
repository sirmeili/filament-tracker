<script lang="ts">
  // The RollCall mark (docs/mockups/logo/rollcall-logo.svg).
  let { size = 30 }: { size?: number } = $props();
</script>

<svg width={size} height={size} viewBox="0 0 140 140" aria-hidden="true">
  <circle cx="70" cy="70" r="62" fill="#C8324B"></circle>
  <circle cx="70" cy="70" r="50" fill="none" stroke="#FFF7F5" stroke-width="4" opacity="0.45"
  ></circle>
  <circle cx="70" cy="70" r="40" fill="none" stroke="#FFF7F5" stroke-width="4" opacity="0.45"
  ></circle>
  <circle cx="70" cy="70" r="30" fill="#FFF7F5"></circle>
  <polyline
    points="56,71 66,81 85,60"
    fill="none"
    stroke="#C8324B"
    stroke-width="9"
    stroke-linecap="round"
    stroke-linejoin="round"
  ></polyline>
</svg>
