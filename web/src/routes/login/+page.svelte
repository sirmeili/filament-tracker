<script lang="ts">
  import { page } from "$app/state";
  import { session } from "#lib/auth/session.svelte.ts";
  import LoginForm from "#lib/components/LoginForm.svelte";
</script>

<LoginForm {session} expired={page.url.searchParams.get("expired") === "1"} />
