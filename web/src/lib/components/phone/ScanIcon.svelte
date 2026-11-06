<script lang="ts">
  /** A phone with NFC waves: the Scan screen's target, and the full app's way back to Scan. */
  let { size = 24 }: { size?: number } = $props();
</script>

<svg
  width={size}
  height={size}
  viewBox="0 0 48 48"
  fill="none"
  stroke="currentColor"
  stroke-width="2.6"
  stroke-linecap="round"
  aria-hidden="true"
>
  <rect x="14" y="6" width="20" height="36" rx="4"></rect>
  <path d="M21 37h6"></path>
  <path d="M38 18a9 9 0 0 1 0 12M42 14a15 15 0 0 1 0 20"></path>
</svg>
