<script lang="ts">
  import { onMount } from 'svelte';
  import { authStore } from './lib/stores/auth';
  import ChatContainer from './lib/components/ChatContainer.svelte';

  onMount(() => {
    // Try to load user from stored token
    authStore.loadUser();
  });
</script>

<ChatContainer />
