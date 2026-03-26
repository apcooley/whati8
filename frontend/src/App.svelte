<script lang="ts">
  import { onMount } from 'svelte';
  import { authStore } from './lib/stores/auth';
  import NavShell from './lib/components/NavShell.svelte';

  onMount(() => {
    // Try to load user from stored token
    authStore.loadUser();
  });
</script>

<NavShell />
