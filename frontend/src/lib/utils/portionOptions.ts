/**
 * Shared portion-option building logic.
 *
 * Used by QuickLogSheet, EditLogSheet, and RecipeIngredientRow to produce
 * a uniform dropdown of portion choices from either rich Food objects or
 * flat API responses.
 */

export interface PortionOption {
  label: string;
  gram_weight: number;
  default_qty: number;
}

/** Strings that indicate a portion should be skipped. */
const SKIP_MODS = ['nlea serving', 'quantity not specified'];

/**
 * Build portion options from rich Food.portions objects (as stored on
 * UserFood.food.portions).  Used by QuickLogSheet.
 */
export function buildPortionOptions(
  portions: Array<{
    modifier?: string | null;
    unit_name?: string | null;
    portion_description?: string | null;
    gram_weight: number;
    amount: number;
  }>,
): PortionOption[] {
  const opts: PortionOption[] = [];

  for (const p of portions) {
    const mod = (p.modifier ?? '').toLowerCase();
    const unit = (p.unit_name ?? '').toLowerCase();
    const desc = (p.portion_description ?? '').toLowerCase();

    if (SKIP_MODS.some(s => mod.includes(s) || desc.includes(s))) continue;
    if (desc === 'grams' || desc === 'oz') continue;

    let label: string;
    const cleanDesc = (p.portion_description || '').replace(/^[\d.]+ undetermined /, '');
    if (cleanDesc && cleanDesc !== 'grams' && cleanDesc !== 'oz') {
      label = cleanDesc;
    } else if (p.modifier && unit !== 'undetermined') {
      label = `${p.modifier} (${Math.round(p.gram_weight)}g)`;
    } else if (p.modifier) {
      label = `${p.modifier} (${Math.round(p.gram_weight)}g)`;
    } else if (unit !== 'undetermined' && unit !== 'g') {
      label = `${p.unit_name} (${Math.round(p.gram_weight)}g)`;
    } else {
      continue;
    }

    opts.push({ label, gram_weight: p.gram_weight, default_qty: p.amount });
  }

  appendFallbacks(opts);
  return opts;
}

/**
 * Build portion options from the flat `/foods/{id}/portions` API response.
 * Used by RecipeIngredientRow and EditLogSheet.
 */
export function buildPortionOptionsFromApi(
  portions: Array<{ description: string; gram_weight: number }>,
): PortionOption[] {
  const opts: PortionOption[] = portions
    .filter(p => !SKIP_MODS.some(s => p.description.toLowerCase().includes(s)))
    .filter(p => p.description !== 'grams' && p.description !== 'oz')
    .map(p => ({
      label: p.description,
      gram_weight: p.gram_weight,
      default_qty: 1,
    }));

  appendFallbacks(opts);
  return opts;
}

/** Ensure grams and oz are always available as fallback options. */
function appendFallbacks(opts: PortionOption[]): void {
  if (!opts.some(o => o.label.toLowerCase() === 'grams')) {
    opts.push({ label: 'grams', gram_weight: 1, default_qty: 100 });
  }
  if (!opts.some(o => o.label.toLowerCase().startsWith('oz'))) {
    opts.push({ label: 'oz', gram_weight: 28.35, default_qty: 1 });
  }
}
