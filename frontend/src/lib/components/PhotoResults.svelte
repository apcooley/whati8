<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { RecognizedItem } from '../api/photo';

  export let items: RecognizedItem[] = [];

  const dispatch = createEventDispatcher<{
    save: { item: RecognizedItem; custom_unit: string | null; default_quantity: number; weight_per_unit: number; volume_ml: number | null };
    close: void;
  }>();

  const CORE_NUTRIENTS = ['calories', 'protein_g', 'fat_g', 'carbs_g', 'fiber_g'];
  
  const NUTRIENT_LABELS: Record<string, string> = {
    calories: 'Calories', protein_g: 'Protein (g)', fat_g: 'Fat (g)',
    saturated_fat_g: 'Sat. Fat (g)', trans_fat_g: 'Trans Fat (g)',
    carbs_g: 'Carbs (g)', fiber_g: 'Fiber (g)', sugars_g: 'Sugars (g)',
    added_sugars_g: 'Added Sugars (g)', cholesterol_mg: 'Cholesterol (mg)',
    sodium_mg: 'Sodium (mg)', vitamin_d_mcg: 'Vitamin D (mcg)',
    calcium_mg: 'Calcium (mg)', iron_mg: 'Iron (mg)', potassium_mg: 'Potassium (mg)',
    vitamin_a_mcg: 'Vitamin A (mcg)', vitamin_c_mg: 'Vitamin C (mg)',
    vitamin_e_mg: 'Vitamin E (mg)', vitamin_k_mcg: 'Vitamin K (mcg)',
    thiamin_mg: 'Thiamin (mg)', riboflavin_mg: 'Riboflavin (mg)',
    niacin_mg: 'Niacin (mg)', vitamin_b6_mg: 'Vitamin B6 (mg)',
    folate_mcg: 'Folate (mcg)', vitamin_b12_mcg: 'Vitamin B12 (mcg)',
    biotin_mcg: 'Biotin (mcg)', pantothenic_acid_mg: 'Pantothenic Acid (mg)',
    phosphorus_mg: 'Phosphorus (mg)', iodine_mcg: 'Iodine (mcg)',
    magnesium_mg: 'Magnesium (mg)', zinc_mg: 'Zinc (mg)',
    selenium_mcg: 'Selenium (mcg)', copper_mg: 'Copper (mg)',
    manganese_mg: 'Manganese (mg)', chromium_mcg: 'Chromium (mcg)',
    molybdenum_mcg: 'Molybdenum (mcg)', chloride_mg: 'Chloride (mg)',
  };

  const ALL_OPTIONAL = Object.keys(NUTRIENT_LABELS).filter(k => !CORE_NUTRIENTS.includes(k));

  let editItems: Array<{
    name: string;
    custom_unit: string;
    custom_qty: string;
    volume_amount: string;
    volume_unit: string;
    weight_g: string;
    nutrients: Record<string, number>;
    expanded: boolean;
    extraNutrients: string[];
  }> = [];

  $: if (items.length > 0 && editItems.length !== items.length) {
    editItems = items.map(item => {
      // Ensure core nutrients have defaults
      const nutrients = { calories: 0, protein_g: 0, fat_g: 0, carbs_g: 0, fiber_g: 0, ...item.nutrients };
      const extra = Object.keys(nutrients).filter(k => !CORE_NUTRIENTS.includes(k));
      // Parse serving description for custom unit and volume
      const desc = item.serving_description || '';
      let customUnit = '';
      let volumeAmount = '';
      let volumeUnit = '';
      
      // Extract custom unit: "1 bottle (...)" → "bottle"
      const unitMatch = desc.match(/^[\d.]+ (\w[\w\s]*?)(?:\s*\(|$)/);
      if (unitMatch) {
        const u = unitMatch[1].trim().toLowerCase();
        if (!['g', 'oz', 'ml', 'gram', 'grams', 'ounce'].includes(u)) {
          customUnit = unitMatch[1].trim();
        }
      }
      
      // Extract volume: "11 fl oz", "325 ml", "0.75 cup", "2 tbsp", etc.
      const volumePatterns = [
        { regex: /([\d.]+)\s*tsp/i, unit: 'tsp' },
        { regex: /([\d.]+)\s*tbsp/i, unit: 'tbsp' },
        { regex: /([\d.]+)\s*fl\.?\s*oz/i, unit: 'fl oz' },
        { regex: /([\d.]+)\s*cup/i, unit: 'cup' },
        { regex: /([\d.]+)\s*pint/i, unit: 'pint' },
        { regex: /([\d.]+)\s*quart/i, unit: 'quart' },
        { regex: /([\d.]+)\s*L\b/i, unit: 'L' },
        { regex: /([\d.]+)\s*m[lL]/i, unit: 'mL' },
      ];
      
      for (const pattern of volumePatterns) {
        const match = desc.match(pattern.regex);
        if (match) {
          volumeAmount = match[1];
          volumeUnit = pattern.unit;
          break;
        }
      }
      
      // Parse quantity from serving description: "6 crackers" → qty=6
      let customQty = '1';
      if (customUnit) {
        const qtyMatch = (item.serving_description || '').match(/^([\d.]+)\s/);
        if (qtyMatch) customQty = qtyMatch[1];
      }

      return {
        name: item.name,
        custom_unit: customUnit,
        custom_qty: customQty,
        volume_amount: volumeAmount,
        volume_unit: volumeUnit,
        weight_g: String(item.serving_size_g || 100),
        nutrients,
        expanded: extra.length > 0,
        extraNutrients: extra,
      };
    });
  }

  function removeNutrient(i: number, key: string) {
    editItems[i].extraNutrients = editItems[i].extraNutrients.filter(k => k !== key);
    delete editItems[i].nutrients[key];
    editItems = editItems;
  }

  function addNutrient(i: number) {
    const used = new Set([...CORE_NUTRIENTS, ...editItems[i].extraNutrients]);
    const available = ALL_OPTIONAL.filter(k => !used.has(k));
    if (available.length > 0) {
      editItems[i].extraNutrients = [...editItems[i].extraNutrients, available[0]];
      editItems[i].nutrients[available[0]] = 0;
      editItems[i].expanded = true;
      editItems = editItems;
    }
  }

  function handleSave(idx: number) {
    const VOLUME_TO_ML: Record<string, number> = {
      tsp: 4.929,
      tbsp: 14.787,
      'fl oz': 29.5735,
      cup: 236.588,
      pint: 473.176,
      quart: 946.353,
      L: 1000,
      mL: 1,
    };
    
    const e = editItems[idx];
    const weightG = parseFloat(e.weight_g) || items[idx].serving_size_g;
    
    // Convert volume amount + unit to mL
    let volMl: number | null = null;
    if (e.volume_amount && e.volume_unit) {
      const amount = parseFloat(e.volume_amount);
      const factor = VOLUME_TO_ML[e.volume_unit];
      if (amount && factor) {
        volMl = amount * factor;
      }
    }
    
    const unit = e.custom_unit?.trim() || null;
    
    // Sanitize nutrients: convert undefined/NaN to 0
    const cleanNutrients: Record<string, number> = {};
    for (const [k, v] of Object.entries(e.nutrients)) {
      cleanNutrients[k] = (typeof v === 'number' && !isNaN(v)) ? v : 0;
    }
    
    const qty = parseFloat(e.custom_qty) || 1;
    let desc = '';
    if (unit) {
      desc = `${qty} ${unit}`;
      const parts: string[] = [];
      if (volMl) {
        // Include original volume amount + unit in description
        parts.push(`${e.volume_amount} ${e.volume_unit}`);
      }
      parts.push(`${weightG}g`);
      desc += ` (${parts.join(', ')})`;
    } else {
      desc = `${weightG}g`;
    }
    
    const weightPerUnit = qty > 0 ? weightG / qty : weightG;
    
    dispatch('save', {
      item: {
        name: e.name,
        serving_description: desc,
        serving_size_g: weightG,
        confidence: items[idx]?.confidence || 'medium',
        nutrients: cleanNutrients,
      },
      custom_unit: unit,
      default_quantity: qty,
      weight_per_unit: weightPerUnit,
      volume_ml: volMl,
    });
  }
</script>

{#each editItems as item, idx}
<div class="bg-white rounded-xl border border-gray-200 overflow-hidden mb-3">
  <div class="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
    <h3 class="font-semibold text-gray-900 text-sm">🍽️ Identified Food</h3>
    <button type="button" on:click={() => dispatch('close')}
      class="text-gray-400 hover:text-gray-600 text-lg leading-none">✕</button>
  </div>

  <div class="p-4 space-y-3">
    <div>
      <label class="block text-xs font-medium text-gray-500 mb-1">Name</label>
      <input type="text" bind:value={item.name}
        class="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm font-semibold" />
    </div>

    <!-- Serving unit/size section -->
    <div class="grid grid-cols-2 gap-2">
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Custom Unit <span class="text-gray-400">(optional)</span></label>
        <input type="text" bind:value={item.custom_unit} placeholder="bottle, bar, slice..."
          class="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm" />
      </div>
      <div class="grid grid-cols-2 gap-2">
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">Qty per serving</label>
          <input type="number" bind:value={item.custom_qty} step="any" min="0.1"
            class="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm" />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-500 mb-1">Total weight (g)</label>
          <input type="number" bind:value={item.weight_g} step="any" min="0"
            class="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm" />
        </div>
      </div>
    </div>

    <div class="grid grid-cols-2 gap-2">
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Volume amount <span class="text-gray-400">(optional)</span></label>
        <input type="number" bind:value={item.volume_amount} step="any" min="0" placeholder="e.g. 0.75"
          class="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm" />
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-500 mb-1">Volume unit</label>
        <select bind:value={item.volume_unit}
          class="w-full px-3 py-2 border border-gray-300 rounded-xl text-sm">
          <option value="">-- none --</option>
          <option value="tsp">tsp</option>
          <option value="tbsp">tbsp</option>
          <option value="fl oz">fl oz</option>
          <option value="cup">cup</option>
          <option value="pint">pint</option>
          <option value="quart">quart</option>
          <option value="L">L</option>
          <option value="mL">mL</option>
        </select>
      </div>
    </div>

    <!-- Core nutrients -->
    <div class="grid grid-cols-2 gap-2">
      {#each CORE_NUTRIENTS as key}
        <div class="rounded-lg p-2.5 {key === 'calories' ? 'bg-orange-50 col-span-2' : 'bg-gray-50'}">
          <label class="block text-xs text-gray-500 mb-0.5">{NUTRIENT_LABELS[key]}</label>
          <input type="number" bind:value={item.nutrients[key]} step="any" min="0"
            class="w-full bg-transparent text-sm font-semibold {key === 'calories' ? 'text-orange-600' : 'text-gray-900'} border-0 p-0 focus:ring-0" />
        </div>
      {/each}
    </div>

    <!-- Extra nutrients -->
    <button type="button" on:click={() => { item.expanded = !item.expanded; editItems = editItems; }}
      class="text-xs text-primary-600 font-medium flex items-center gap-1">
      <svg class="w-3 h-3 transition-transform {item.expanded ? 'rotate-90' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
      </svg>
      {item.expanded ? 'Hide' : 'Show'} additional nutrients ({item.extraNutrients.length})
    </button>

    {#if item.expanded}
      <div class="space-y-2">
        {#each item.extraNutrients as key}
          <div class="flex items-center gap-2">
            <div class="flex-1 rounded-lg bg-gray-50 p-2.5">
              <label class="block text-xs text-gray-500 mb-0.5">{NUTRIENT_LABELS[key] || key}</label>
              <input type="number" bind:value={item.nutrients[key]} step="any" min="0"
                class="w-full bg-transparent text-sm font-medium text-gray-900 border-0 p-0 focus:ring-0" />
            </div>
            <button type="button" on:click={() => removeNutrient(idx, key)}
              class="w-7 h-7 flex items-center justify-center rounded-full text-gray-300 hover:text-red-500 hover:bg-red-50 flex-shrink-0">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        {/each}
      </div>

      <button type="button" on:click={() => addNutrient(idx)}
        class="w-full py-2 border-2 border-dashed border-gray-300 rounded-xl text-xs text-gray-500 font-medium hover:border-primary-400 hover:text-primary-600">
        + Add Nutrient
      </button>
    {/if}

    <button type="button" on:click={() => handleSave(idx)}
      class="w-full py-2.5 bg-primary-600 text-white rounded-xl font-semibold text-sm hover:bg-primary-700">
      Add to My Foods
    </button>
  </div>
</div>
{/each}
