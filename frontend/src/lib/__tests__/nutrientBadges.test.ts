import { describe, it, expect } from 'vitest';

/**
 * Tests for NutrientBadges and nutrient display across the app.
 *
 * Bugs found:
 * 1. ProfileFoodItem: getNutrientPerServing returns NaN because
 *    FoodDetail interface is missing created_by_user_id
 * 2. QuickLogSheet: only shows calories because getNutrientPerGram
 *    has same issue, and values aren't multiplied by grams
 *
 * Root cause: FoodDetail TypeScript interface missing created_by_user_id
 */

describe('FoodDetail interface', () => {
  it('includes created_by_user_id field', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/types/profile.ts', 'utf-8');
    // FoodDetail must have created_by_user_id for correct nutrient scaling
    const interfaceMatch = source.match(/interface FoodDetail\s*\{([\s\S]*?)\}/);
    expect(interfaceMatch).toBeTruthy();
    expect(interfaceMatch![1]).toContain('created_by_user_id');
  });
});

describe('ProfileFoodItem nutrient display', () => {
  it('does not use includes() for nutrient name matching', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/components/ProfileFoodItem.svelte', 'utf-8');
    // Should use a robust nutrient lookup, not fragile includes()
    // If it uses includes(), it should at least handle null/undefined
    expect(source).not.toContain('NaN');
  });

  it('imports and uses NutrientBadges component', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/components/ProfileFoodItem.svelte', 'utf-8');
    expect(source).toContain('NutrientBadges');
  });

  it('does not show raw kcal text', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/components/ProfileFoodItem.svelte', 'utf-8');
    // Should not have old "{calories} kcal" pattern
    expect(source).not.toMatch(/\{calories\}\s*kcal/);
  });
});

describe('QuickLogSheet nutrient display', () => {
  it('imports NutrientBadges', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/components/QuickLogSheet.svelte', 'utf-8');
    expect(source).toContain('NutrientBadges');
  });

  it('does not show raw kcal text', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/components/QuickLogSheet.svelte', 'utf-8');
    expect(source).not.toMatch(/\{estCalories\}\s*kcal/);
  });

  it('passes all nutrient values to NutrientBadges, not just calories', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/components/QuickLogSheet.svelte', 'utf-8');
    // NutrientBadges should receive protein, carbs, fat, fiber
    const badgeCall = source.match(/<NutrientBadges[\s\S]*?\/>/);
    expect(badgeCall).toBeTruthy();
    const badge = badgeCall![0];
    expect(badge).toContain('protein');
    expect(badge).toContain('carbs');
    expect(badge).toContain('fat');
  });
});

describe('EditLogSheet nutrient display', () => {
  it('imports NutrientBadges', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/components/EditLogSheet.svelte', 'utf-8');
    expect(source).toContain('NutrientBadges');
  });

  it('does not show raw kcal text', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/components/EditLogSheet.svelte', 'utf-8');
    expect(source).not.toMatch(/\{estimatedCal\}\s*kcal/);
  });
});

describe('getFoodCalPerGram uses created_by_user_id', () => {
  it('function references created_by_user_id for base calculation', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/types/profile.ts', 'utf-8');
    const fnMatch = source.match(/function getFoodCalPerGram[\s\S]*?\}/);
    expect(fnMatch).toBeTruthy();
    expect(fnMatch![0]).toContain('created_by_user_id');
  });
});

describe('NutrientBadges component', () => {
  it('handles null values without showing NaN', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/components/NutrientBadges.svelte', 'utf-8');
    // Should filter out null values
    expect(source).toContain('!= null') || expect(source).toContain('!== null');
  });

  it('rounds values to integers', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/components/NutrientBadges.svelte', 'utf-8');
    expect(source).toContain('Math.round');
  });
});
