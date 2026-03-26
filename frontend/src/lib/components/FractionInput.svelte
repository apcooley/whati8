<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { parseFraction } from '../utils/parseFraction';

  export let value: string = '';

  const dispatch = createEventDispatcher<{ change: string }>();

  let fractionMode = false;
  let decimalStr = value;
  let fractionStr = '';

  function switchToDecimal() {
    if (!fractionMode) return;
    // Convert fraction to decimal if valid
    if (fractionStr) {
      const result = parseFraction(fractionStr);
      if (result !== null) {
        decimalStr = String(parseFloat(result.toFixed(4)));
      }
    }
    fractionMode = false;
    value = decimalStr;
    dispatch('change', value);
  }

  function switchToFraction() {
    if (fractionMode) return;
    // Save current decimal
    decimalStr = value;
    fractionMode = true;
    value = fractionStr;
    dispatch('change', value);
  }

  function onInput() {
    if (fractionMode) {
      fractionStr = value;
    } else {
      decimalStr = value;
    }
    dispatch('change', value);
  }
</script>

<div>
  <input
    type="text"
    inputmode={fractionMode ? 'text' : 'decimal'}
    bind:value
    on:input={onInput}
    placeholder={fractionMode ? 'e.g. 1/3' : ''}
    class="w-full px-3 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
  />
  <div class="flex items-center gap-1 mt-1">
    <button type="button"
      on:click={switchToDecimal}
      class="text-xs px-2 py-0.5 rounded-full transition-colors {!fractionMode ? 'bg-primary-100 text-primary-700 font-semibold' : 'text-gray-400 hover:text-gray-600'}"
    >0.5</button>
    <span class="text-gray-300 text-xs">·</span>
    <button type="button"
      on:click={switchToFraction}
      class="text-xs px-2 py-0.5 rounded-full transition-colors {fractionMode ? 'bg-primary-100 text-primary-700 font-semibold' : 'text-gray-400 hover:text-gray-600'}"
    >1/2</button>
  </div>
</div>
