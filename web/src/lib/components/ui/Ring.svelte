<script lang="ts">
  import { swatchColor } from "#lib/format.ts";

  /** Spool ring swatch: a thick border in the tag's color around a hole in the page
   * background. Decorative; the product name says what it is. */
  interface Props {
    rgba: string;
    size?: "sm" | "md" | "lg";
  }

  let { rgba, size = "md" }: Props = $props();
</script>

<span class="ring {size}" aria-hidden="true" style:border-color={swatchColor(rgba)}></span>

<style>
  .ring {
    display: inline-block;
    flex: none;
    border-radius: 50%;
    border-style: solid;
    background: var(--bg);
    box-shadow: var(--ringShadow), var(--holeShadow);
  }

  .sm {
    width: 30px;
    height: 30px;
    border-width: 8px;
    box-shadow: var(--ringShadowSmall);
  }

  .md {
    width: 58px;
    height: 58px;
    border-width: 15px;
  }

  .lg {
    width: 104px;
    height: 104px;
    border-width: 28px;
  }
</style>
