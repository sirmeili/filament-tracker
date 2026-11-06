<script lang="ts">
  import { qrPath } from "#lib/pairing.ts";

  interface Props {
    text: string;
    label: string;
  }

  let { text, label }: Props = $props();
  const qr = $derived(qrPath(text));
</script>

<svg
  role="img"
  aria-label={label}
  viewBox="0 0 {qr.size} {qr.size}"
  shape-rendering="crispEdges"
  width="240"
  height="240"
>
  <rect width={qr.size} height={qr.size} fill="#fff" />
  <path d={qr.path} fill="#000" />
</svg>

<style>
  svg {
    display: block;
    max-width: 100%;
    height: auto;
    border-radius: 8px;
  }
</style>
