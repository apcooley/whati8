<script lang="ts">
  import { authStore } from '../stores/auth';

  let mode: 'login' | 'register' = 'login';
  let username = '';
  let email = '';
  let password = '';
  let confirmPassword = '';
  let error = '';
  let loading = false;

  async function handleSubmit() {
    error = '';

    // Validation
    if (mode === 'register') {
      if (!email) {
        error = 'Email is required';
        return;
      }
      if (password.length < 8) {
        error = 'Password must be at least 8 characters';
        return;
      }
      if (password !== confirmPassword) {
        error = 'Passwords do not match';
        return;
      }
    }

    loading = true;
    try {
      if (mode === 'register') {
        await authStore.register(username, email, password);
      } else {
        await authStore.login(username, password);
      }
    } catch (err: any) {
      error = err?.message || (mode === 'register' ? 'Registration failed' : 'Login failed');
      loading = false;
    }
  }

  function toggleMode() {
    mode = mode === 'login' ? 'register' : 'login';
    error = '';
  }
</script>

<div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
  <div class="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
    <h2 class="text-2xl font-bold text-gray-900 mb-2">
      {mode === 'login' ? 'Sign in to whati8' : 'Create your account'}
    </h2>
    <p class="text-sm text-gray-600 mb-6">
      {mode === 'login'
        ? 'Track your food with AI-powered nutrition insights'
        : 'Start tracking your nutrition today'}
    </p>

    <form on:submit|preventDefault={handleSubmit} class="space-y-4">
      {#if error}
        <div class="bg-red-50 text-red-700 p-3 rounded-md text-sm">
          {error}
        </div>
      {/if}

      <div>
        <label for="username" class="block text-sm font-medium text-gray-700 mb-1">
          Username
        </label>
        <input
          id="username"
          type="text"
          bind:value={username}
          required
          disabled={loading}
          minlength="3"
          maxlength="50"
          class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
        />
      </div>

      {#if mode === 'register'}
        <div>
          <label for="email" class="block text-sm font-medium text-gray-700 mb-1">
            Email
          </label>
          <input
            id="email"
            type="email"
            bind:value={email}
            required
            disabled={loading}
            class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
      {/if}

      <div>
        <label for="password" class="block text-sm font-medium text-gray-700 mb-1">
          Password
        </label>
        <input
          id="password"
          type="password"
          bind:value={password}
          required
          disabled={loading}
          minlength="8"
          class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
        />
        {#if mode === 'register'}
          <p class="text-xs text-gray-500 mt-1">At least 8 characters</p>
        {/if}
      </div>

      {#if mode === 'register'}
        <div>
          <label for="confirmPassword" class="block text-sm font-medium text-gray-700 mb-1">
            Confirm Password
          </label>
          <input
            id="confirmPassword"
            type="password"
            bind:value={confirmPassword}
            required
            disabled={loading}
            minlength="8"
            class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
      {/if}

      <button
        type="submit"
        disabled={loading}
        class="w-full bg-primary-600 text-white py-2 px-4 rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading
          ? (mode === 'login' ? 'Signing in...' : 'Creating account...')
          : (mode === 'login' ? 'Sign in' : 'Create account')}
      </button>
    </form>

    <div class="mt-6 text-center">
      <button type="button"
        on:click={toggleMode}
        disabled={loading}
        class="text-sm text-primary-600 hover:text-primary-700 disabled:opacity-50"
      >
        {mode === 'login'
          ? "Don't have an account? Sign up"
          : 'Already have an account? Sign in'}
      </button>
    </div>
  </div>
</div>
