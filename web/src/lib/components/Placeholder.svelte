<script lang="ts">
  interface Props {
    title: string;
    /** What the page will show, from the Server: web UI table in docs/SPEC.md. */
    shows: string;
  }

  let { title, shows }: Props = $props();
</script>

<section>
  <h1>{title}</h1>
  <p>{shows}</p>
  <p class="muted">This page is being built in a later part of M2.</p>
</section>
