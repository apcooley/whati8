<script lang="ts">
  /**
   * Renders emoji nutrient badges from either:
   * - summary_nutrients array (from daily log entries)
   * - raw nutrient values (calories, protein, carbs, fat, fiber)
   */

  export let summaryNutrients: Array<{ name: string; value: number; unit?: string }> | null = null;
  export let calories: number | null = null;
  export let protein: number | null = null;
  export let carbs: number | null = null;
  export let fat: number | null = null;
  export let fiber: number | null = null;
  export let scale: number = 1; // multiply raw values by this (e.g. for quantity)
  export let size: 'xs' | 'sm' = 'xs';

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

  function safeRound(v: number | null, s: number): number | null {
    if (v == null || !Number.isFinite(v) || !Number.isFinite(s)) return null;
    const result = Math.round(v * s);
    return Number.isFinite(result) ? result : null;
  }

  // Build badges from either source — NaN/Infinity protection throughout
  $: badges = summaryNutrients
    ? summaryNutrients.filter(sn => sn.value !== 0 && Number.isFinite(sn.value))
    : [
        calories != null ? { name: 'Calories', value: safeRound(calories, scale) } : null,
        protein != null ? { name: 'Protein', value: safeRound(protein, scale) } : null,
        fiber != null ? { name: 'Fiber', value: safeRound(fiber, scale) } : null,
        carbs != null ? { name: 'Carbs', value: safeRound(carbs, scale) } : null,
        fat != null ? { name: 'Fat', value: safeRound(fat, scale) } : null,
      ].filter((b): b is { name: string; value: number } => b !== null && b.value !== null && b.value !== 0);
</script>

{#if badges.length > 0}
  <span class="inline-flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
    {#each badges as b}
      <span class="text-{size}" title={b.name}>
        {#if isText(b.name)}<code class="font-mono text-[10px] bg-gray-100 px-0.5 rounded">{getEmoji(b.name)}</code>{:else}{getEmoji(b.name)}{/if}<span class="font-medium text-gray-700">{b.value}</span>
      </span>
    {/each}
  </span>
{/if}
