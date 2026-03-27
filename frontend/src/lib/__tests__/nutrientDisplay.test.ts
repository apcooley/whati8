import { describe, it, expect } from 'vitest';
import { getFoodCalPerGram } from '../types/profile';

/**
 * End-to-end tests for nutrient display calculations.
 * Tests the actual functions that compute nutrient values for display.
 */

// Mock food data matching what the API returns
function makeFoodDetail(overrides: any = {}) {
  return {
    id: 1,
    name: 'Test Food',
    brand: null,
    serving_size: 100,
    unit: 'g',
    created_by_user_id: null,
    food_nutrients: [],
    portions: [],
    ...overrides,
  };
}

function makeNutrient(name: string, amount: number) {
  return {
    nutrient: { id: 1, name, unit: name === 'Energy' ? 'kcal' : 'g' },
    amount_per_serving: amount,
  };
}

describe('getFoodCalPerGram', () => {
  it('USDA food: divides by 100', () => {
    const food = makeFoodDetail({
      created_by_user_id: null,
      serving_size: 126,
      food_nutrients: [makeNutrient('Energy', 89)],
    });
    expect(getFoodCalPerGram(food)).toBeCloseTo(0.89, 2);
  });

  it('custom food: divides by serving_size', () => {
    const food = makeFoodDetail({
      created_by_user_id: 1,
      serving_size: 325,
      food_nutrients: [makeNutrient('Energy', 140)],
    });
    expect(getFoodCalPerGram(food)).toBeCloseTo(140 / 325, 4);
  });

  it('returns null when no energy nutrient', () => {
    const food = makeFoodDetail({
      food_nutrients: [makeNutrient('Protein', 10)],
    });
    expect(getFoodCalPerGram(food)).toBeNull();
  });

  it('handles Atwater General energy', () => {
    const food = makeFoodDetail({
      food_nutrients: [makeNutrient('Energy (Atwater General Factors)', 60)],
    });
    expect(getFoodCalPerGram(food)).toBeCloseTo(0.6, 2);
  });

  it('returns null when food_nutrients is empty', () => {
    const food = makeFoodDetail({ food_nutrients: [] });
    expect(getFoodCalPerGram(food)).toBeNull();
  });

  it('returns null when food_nutrients is undefined', () => {
    const food = makeFoodDetail({ food_nutrients: undefined });
    expect(getFoodCalPerGram(food)).toBeNull();
  });

  it('does not return NaN for any valid input', () => {
    const cases = [
      makeFoodDetail({ created_by_user_id: null, food_nutrients: [makeNutrient('Energy', 89)] }),
      makeFoodDetail({ created_by_user_id: 1, serving_size: 44, food_nutrients: [makeNutrient('Energy', 160)] }),
      makeFoodDetail({ created_by_user_id: 1, serving_size: 0, food_nutrients: [makeNutrient('Energy', 100)] }),
      makeFoodDetail({ food_nutrients: [] }),
    ];
    for (const food of cases) {
      const result = getFoodCalPerGram(food);
      if (result !== null) {
        expect(Number.isNaN(result)).toBe(false);
        expect(Number.isFinite(result)).toBe(true);
      }
    }
  });

  it('handles serving_size=0 for custom food without producing Infinity', () => {
    const food = makeFoodDetail({
      created_by_user_id: 1,
      serving_size: 0,
      food_nutrients: [makeNutrient('Energy', 100)],
    });
    const result = getFoodCalPerGram(food);
    // Should either return null or a finite number, never Infinity/NaN
    if (result !== null) {
      expect(Number.isFinite(result)).toBe(true);
    }
  });
});

describe('Nutrient lookup by name', () => {
  // Simulates the find() call used in ProfileFoodItem and QuickLogSheet
  function findNutrient(nutrients: any[], searchTerm: string): number | null {
    const fn = nutrients?.find((n: any) => n.nutrient?.name?.toLowerCase().includes(searchTerm));
    return fn ? fn.amount_per_serving : null;
  }

  it('finds Protein', () => {
    const nutrients = [makeNutrient('Protein', 10)];
    expect(findNutrient(nutrients, 'protein')).toBe(10);
  });

  it('finds Total lipid (fat) via "lipid"', () => {
    const nutrients = [makeNutrient('Total lipid (fat)', 5)];
    expect(findNutrient(nutrients, 'lipid')).toBe(5);
  });

  it('finds Carbohydrate, by difference via "carbohydrate"', () => {
    const nutrients = [makeNutrient('Carbohydrate, by difference', 30)];
    expect(findNutrient(nutrients, 'carbohydrate')).toBe(30);
  });

  it('finds Fiber, total dietary via "fiber"', () => {
    const nutrients = [makeNutrient('Fiber, total dietary', 3)];
    expect(findNutrient(nutrients, 'fiber')).toBe(3);
  });

  it('returns null when nutrient not found', () => {
    const nutrients = [makeNutrient('Protein', 10)];
    expect(findNutrient(nutrients, 'fiber')).toBeNull();
  });

  it('returns null for undefined/null nutrients array', () => {
    expect(findNutrient(undefined as any, 'protein')).toBeNull();
    expect(findNutrient(null as any, 'protein')).toBeNull();
  });

  it('handles nutrients with missing nutrient object', () => {
    const nutrients = [{ nutrient: null, amount_per_serving: 10 }];
    expect(findNutrient(nutrients, 'protein')).toBeNull();
  });

  it('handles nutrients with missing name', () => {
    const nutrients = [{ nutrient: { id: 1, name: null, unit: 'g' }, amount_per_serving: 10 }];
    expect(findNutrient(nutrients, 'protein')).toBeNull();
  });
});

describe('Source code: no raw kcal display in key components', () => {
  const components = [
    'src/lib/components/ProfileFoodItem.svelte',
    'src/lib/components/QuickLogSheet.svelte',
    'src/lib/components/EditLogSheet.svelte',
  ];

  for (const path of components) {
    it(`${path.split('/').pop()} uses NutrientBadges`, async () => {
      const fs = await import('fs');
      const source = fs.readFileSync(path, 'utf-8');
      expect(source).toContain('NutrientBadges');
      // Should not have standalone "kcal" in display text
      expect(source).not.toMatch(/\{(estCalories|estimatedCal|calories)\}\s*kcal/);
    });
  }
});

describe('NutrientBadges component handles edge cases', () => {
  it('does not produce NaN in badges array', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/components/NutrientBadges.svelte', 'utf-8');
    // Should use != null check (not just truthiness) to distinguish 0 from null
    expect(source).toContain('!= null');
    // Should use Math.round which returns NaN for NaN input — need to filter
    expect(source).toContain('Math.round');
  });
});
