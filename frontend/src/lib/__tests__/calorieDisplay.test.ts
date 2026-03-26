/**
 * Tests for calorie display calculations across the app.
 * 
 * Key distinction:
 * - USDA foods: amount_per_serving is per 100g
 * - Custom foods (created_by_user_id set): amount_per_serving is per serving_size
 */

import { describe, it, expect } from 'vitest';

// Replicate the food detail structure
interface FoodNutrientDetail {
  nutrient: { name: string; unit: string };
  amount_per_serving: number;
}

interface FoodDetail {
  serving_size: number;
  created_by_user_id: number | null;
  food_nutrients: FoodNutrientDetail[];
  portions?: any[];
  calories?: number;
}

/**
 * Get kcal per gram for a food. This is the universal base.
 * - USDA: amount_per_serving / 100 (nutrients are per 100g)
 * - Custom: amount_per_serving / serving_size (nutrients are per serving)
 */
function getCalPerGram(food: FoodDetail): number | null {
  const n = food.food_nutrients.find(fn =>
    fn.nutrient.name.toLowerCase().includes('energy')
  );
  if (!n) return null;

  let kcal = n.amount_per_serving;
  if (n.nutrient.unit === 'kJ') kcal = kcal / 4.184;

  const base = food.created_by_user_id ? food.serving_size : 100;
  return kcal / (base || 100);
}

/**
 * Get kcal for a specific portion (gram_weight in grams).
 */
function getCalForPortion(food: FoodDetail, gramWeight: number): number {
  const cpg = getCalPerGram(food);
  return cpg ? Math.round(cpg * gramWeight) : 0;
}

/**
 * Get kcal for the food's default serving.
 */
function getCalPerServing(food: FoodDetail): number | null {
  const cpg = getCalPerGram(food);
  if (cpg === null) return null;
  return Math.round(cpg * food.serving_size);
}


// ===== Test fixtures =====

const usdaBanana: FoodDetail = {
  serving_size: 126,  // USDA default serving
  created_by_user_id: null,
  food_nutrients: [
    { nutrient: { name: 'Energy', unit: 'kJ' }, amount_per_serving: 371 },  // per 100g
    { nutrient: { name: 'Protein', unit: 'g' }, amount_per_serving: 1.09 },
  ],
};

const customShake: FoodDetail = {
  serving_size: 325,
  created_by_user_id: 1,
  food_nutrients: [
    { nutrient: { name: 'Energy', unit: 'kJ' }, amount_per_serving: 585.76 },  // 140 kcal per 325g
    { nutrient: { name: 'Protein', unit: 'g' }, amount_per_serving: 30 },
  ],
};

const customBar: FoodDetail = {
  serving_size: 60,
  created_by_user_id: 1,
  food_nutrients: [
    { nutrient: { name: 'Energy', unit: 'kJ' }, amount_per_serving: 836.8 },  // 200 kcal per 60g
  ],
};

const usdaCheese: FoodDetail = {
  serving_size: 17,
  created_by_user_id: null,
  food_nutrients: [
    { nutrient: { name: 'Energy', unit: 'kJ' }, amount_per_serving: 724 },  // per 100g
  ],
};


describe('getCalPerGram', () => {
  it('USDA food: divides by 100', () => {
    const cpg = getCalPerGram(usdaBanana)!;
    // 371 kJ / 4.184 = 88.7 kcal per 100g → 0.887 kcal/g
    expect(cpg).toBeCloseTo(0.887, 2);
  });

  it('custom food: divides by serving_size', () => {
    const cpg = getCalPerGram(customShake)!;
    // 585.76 kJ / 4.184 = 140 kcal per 325g → 0.4308 kcal/g
    expect(cpg).toBeCloseTo(0.4308, 3);
  });

  it('custom bar: divides by serving_size', () => {
    const cpg = getCalPerGram(customBar)!;
    // 836.8 kJ / 4.184 = 200 kcal per 60g → 3.333 kcal/g
    expect(cpg).toBeCloseTo(3.333, 2);
  });
});


describe('getCalPerServing', () => {
  it('USDA banana: serving_size * cal/g', () => {
    const cal = getCalPerServing(usdaBanana)!;
    // 0.887 * 126 = 111.7 → 112 kcal
    expect(cal).toBeCloseTo(112, 0);
  });

  it('custom shake: should be 140 kcal', () => {
    const cal = getCalPerServing(customShake)!;
    expect(cal).toBe(140);
  });

  it('custom bar: should be 200 kcal', () => {
    const cal = getCalPerServing(customBar)!;
    expect(cal).toBe(200);
  });
});


describe('getCalForPortion', () => {
  it('USDA banana medium (118g)', () => {
    const cal = getCalForPortion(usdaBanana, 118);
    expect(cal).toBeCloseTo(105, 0);
  });

  it('custom shake 1 bottle (325g) = 140 kcal', () => {
    const cal = getCalForPortion(customShake, 325);
    expect(cal).toBe(140);
  });

  it('custom shake 1 fl oz (29.57g)', () => {
    const cal = getCalForPortion(customShake, 29.57);
    expect(cal).toBeCloseTo(13, 0);
  });

  it('USDA cheese 1 slice (28g)', () => {
    const cal = getCalForPortion(usdaCheese, 28);
    // 724 kJ / 4.184 = 173 kcal per 100g → 1.73 * 28 = 48.4 → 48
    expect(cal).toBeCloseTo(48, 0);
  });

  it('custom bar 1 bar (60g) = 200 kcal', () => {
    const cal = getCalForPortion(customBar, 60);
    expect(cal).toBe(200);
  });
});


describe('ProfileFoodItem calorie display (current bug)', () => {
  it('BUG: old formula gives wrong calories for custom foods', () => {
    // Old formula: calPer100g * serving_size / 100
    // getFoodCalPer100g returns amount_per_serving / 4.184 (treats ALL as per 100g)
    const oldCalPer100g = 585.76 / 4.184;  // = 140
    const oldResult = Math.round(oldCalPer100g * 325 / 100);  // = 455 ❌
    expect(oldResult).toBe(455);  // This is the bug!
    
    // New formula: getCalPerServing
    const newResult = getCalPerServing(customShake);
    expect(newResult).toBe(140);  // ✅
  });

  it('old formula works for USDA foods (coincidentally)', () => {
    const oldCalPer100g = 371 / 4.184;  // = 88.7
    const oldResult = Math.round(oldCalPer100g * 126 / 100);  // = 112
    expect(oldResult).toBe(112);  // Happens to work because USDA nutrients ARE per 100g
  });
});


describe('QuickLogSheet calorie estimate', () => {
  it('custom food: estimate uses correct base', () => {
    // QuickLogSheet formula: (calories / base) * quantity * portionGrams
    // where base = created_by_user_id ? serving_size : 100
    const base = customShake.created_by_user_id ? customShake.serving_size : 100;
    expect(base).toBe(325);
    
    const calPerServing = 585.76 / 4.184;  // 140 kcal (this is what getFoodCalPer100g returns)
    const estimate = Math.round((calPerServing / base) * 1 * 325);
    expect(estimate).toBe(140);
  });

  it('USDA food: estimate uses 100 as base', () => {
    const base = usdaBanana.created_by_user_id ? usdaBanana.serving_size : 100;
    expect(base).toBe(100);
    
    const calPer100g = 371 / 4.184;
    const estimate = Math.round((calPer100g / base) * 1 * 152);  // extra large banana
    expect(estimate).toBeCloseTo(135, 0);
  });
});
