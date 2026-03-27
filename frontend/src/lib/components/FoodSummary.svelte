<script lang="ts">
  /**
   * Fetches and displays summary nutrients for a food at a given quantity.
   * Uses the server-side compute_food_summary — same logic as daily log view.
   * Single source of truth for nutrient display anywhere in the app.
   */
  import { getFoodSummary, type SummaryNutrient } from '../api/foods';

  export let foodId: number;
  export let quantity: number = 100; // grams
  export let size: 'xs' | 'sm' = 'xs';
  export let prefix: string = ''; // e.g. "≈ "

  const NUTRIENT_EMOJI: Record<string, string> = {
    'calories': '🔥', 'protein': '🥩', 'fiber': '🌾', 'carbs': '🍞', 'fat': '🧈',
  };

  function getEmoji(name: string): string {
    const lower = name.toLowerCase();
    for (const [key, emoji] of Object.entries(NUTRIENT_EMOJI)) {
      if (lower.includes(key)) return emoji;
    }
    return name.replace(/\s*points?$/i, '').trim().slice(0, 2).toUpperCase();
  }

  function isText(name: string): boolean {
    return !Object.keys(NUTRIENT_EMOJI).some(k => name.toLowerCase().includes(k));
  }

  let badges: SummaryNutrient[] = [];
  let lastKey = '';

  $: key = `${foodId}-${quantity}`;
  $: if (key !== lastKey && foodId > 0 && quantity > 0) {
    lastKey = key;
    loadSummary(foodId, quantity);
  }

  async function loadSummary(fid: number, qty: number) {
    try {
      const result = await getFoodSummary(fid, qty);
      // Only update if this is still the current request
      if (`${fid}-${qty}` === lastKey) {
        badges = result.filter(b => b.value !== 0);
      }
    } catch {
      badges = [];
    }
  }
</script>

{#if badges.length > 0}
  <span class="inline-flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
    {#if prefix}<span class="text-{size} text-gray-500">{prefix}</span>{/if}
    {#each badges as b}
      <span class="text-{size}" title="{b.name}: {b.value} {b.unit}">
        {#if isText(b.name)}<code class="font-mono text-[10px] bg-gray-100 px-0.5 rounded">{getEmoji(b.name)}</code>{:else}{getEmoji(b.name)}{/if}<span class="font-medium text-gray-700">{Math.round(b.value)}</span>
      </span>
    {/each}
  </span>
{/if}
