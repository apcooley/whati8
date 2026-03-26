/**
 * Tests for the photo food creation payload builder.
 * 
 * Validates that the payload sent to POST /foods/ is correctly
 * constructed from PhotoResults form data for all 4 serving types.
 */

import { describe, it, expect } from 'vitest';

/** 
 * Extracted payload builder - mirrors the logic in AddFoodView.handlePhotoSave
 * and PhotoResults.handleSave
 */
interface PhotoSaveEvent {
  item: {
    name: string;
    serving_description: string;
    serving_size_g: number;
    confidence: string;
    nutrients: Record<string, number>;
  };
  custom_unit: string | null;
  volume_ml: number | null;
}

interface FoodCreatePayload {
  name: string;
  serving_size: number;
  unit: string;
  gram_weight: number;
  serving_description: string;
  custom_unit?: string;
  volume_ml?: number;
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
  fiber: number;
}

function buildFoodPayload(event: PhotoSaveEvent): FoodCreatePayload {
  const { item, custom_unit, volume_ml } = event;
  const n = item.nutrients || {};
  const servingG = item.serving_size_g || 100;
  const payload: FoodCreatePayload = {
    name: item.name || 'Unknown Food',
    serving_size: servingG,
    unit: custom_unit || 'g',
    gram_weight: servingG,
    serving_description: item.serving_description,
    calories: Number(n.calories) || 0,
    protein: Number(n.protein_g) || 0,
    carbs: Number(n.carbs_g) || 0,
    fat: Number(n.fat_g) || 0,
    fiber: Number(n.fiber_g) || 0,
  };
  if (custom_unit) payload.custom_unit = custom_unit;
  if (volume_ml) payload.volume_ml = volume_ml;
  return payload;
}

/**
 * Extracted from PhotoResults.handleSave - builds the event from form state
 */
interface FormState {
  name: string;
  custom_unit: string;
  volume_ml: string;
  weight_g: string;
  nutrients: Record<string, number>;
}

function buildSaveEvent(form: FormState, origConfidence: string = 'medium'): PhotoSaveEvent {
  const weightG = parseFloat(form.weight_g) || 100;
  const volMl = form.volume_ml ? parseFloat(form.volume_ml) : null;
  const unit = form.custom_unit?.trim() || null;

  // Sanitize nutrients
  const cleanNutrients: Record<string, number> = {};
  for (const [k, v] of Object.entries(form.nutrients)) {
    cleanNutrients[k] = (typeof v === 'number' && !isNaN(v)) ? v : 0;
  }

  let desc = '';
  if (unit) {
    desc = `1 ${unit}`;
    const parts: string[] = [];
    if (volMl) parts.push(`${volMl} mL`);
    parts.push(`${weightG}g`);
    desc += ` (${parts.join(', ')})`;
  } else {
    desc = `${weightG}g`;
  }

  return {
    item: {
      name: form.name,
      serving_description: desc,
      serving_size_g: weightG,
      confidence: origConfidence,
      nutrients: cleanNutrients,
    },
    custom_unit: unit,
    volume_ml: volMl,
  };
}


describe('PhotoResults.handleSave → buildSaveEvent', () => {
  it('Type 1: weight only (40g oats)', () => {
    const event = buildSaveEvent({
      name: 'Steel Cut Oats',
      custom_unit: '',
      volume_ml: '',
      weight_g: '40',
      nutrients: { calories: 150, protein_g: 5, carbs_g: 27, fat_g: 2.5, fiber_g: 4 },
    });

    expect(event.custom_unit).toBeNull();
    expect(event.volume_ml).toBeNull();
    expect(event.item.serving_size_g).toBe(40);
    expect(event.item.serving_description).toBe('40g');
    expect(event.item.nutrients.calories).toBe(150);
  });

  it('Type 2: volume beverage (no custom unit)', () => {
    const event = buildSaveEvent({
      name: 'Orange Juice',
      custom_unit: '',
      volume_ml: '240',
      weight_g: '248',
      nutrients: { calories: 112, protein_g: 2, carbs_g: 26, fat_g: 0.5, fiber_g: 0.5 },
    });

    expect(event.custom_unit).toBeNull();
    expect(event.volume_ml).toBe(240);
    expect(event.item.serving_size_g).toBe(248);
    // No custom unit, so just weight
    expect(event.item.serving_description).toBe('248g');
  });

  it('Type 3: custom unit + weight (1 bar = 60g)', () => {
    const event = buildSaveEvent({
      name: 'Protein Bar',
      custom_unit: 'bar',
      volume_ml: '',
      weight_g: '60',
      nutrients: { calories: 200, protein_g: 20, carbs_g: 22, fat_g: 7, fiber_g: 3 },
    });

    expect(event.custom_unit).toBe('bar');
    expect(event.volume_ml).toBeNull();
    expect(event.item.serving_size_g).toBe(60);
    expect(event.item.serving_description).toBe('1 bar (60g)');
  });

  it('Type 4: custom unit + volume (1 bottle, 325mL, 325g)', () => {
    const event = buildSaveEvent({
      name: 'Protein Shake',
      custom_unit: 'bottle',
      volume_ml: '325',
      weight_g: '325',
      nutrients: { calories: 140, protein_g: 30, carbs_g: 7, fat_g: 1.5, fiber_g: 4 },
    });

    expect(event.custom_unit).toBe('bottle');
    expect(event.volume_ml).toBe(325);
    expect(event.item.serving_size_g).toBe(325);
    expect(event.item.serving_description).toBe('1 bottle (325 mL, 325g)');
  });

  it('sanitizes undefined/NaN nutrients to 0', () => {
    const event = buildSaveEvent({
      name: 'Bad Data',
      custom_unit: '',
      volume_ml: '',
      weight_g: '100',
      nutrients: { calories: undefined as any, protein_g: NaN, carbs_g: 10, fat_g: null as any, fiber_g: 0 },
    });

    expect(event.item.nutrients.calories).toBe(0);
    expect(event.item.nutrients.protein_g).toBe(0);
    expect(event.item.nutrients.carbs_g).toBe(10);
    expect(event.item.nutrients.fat_g).toBe(0);
    expect(event.item.nutrients.fiber_g).toBe(0);
  });

  it('defaults weight to 100 if empty', () => {
    const event = buildSaveEvent({
      name: 'No Weight',
      custom_unit: '',
      volume_ml: '',
      weight_g: '',
      nutrients: { calories: 50 },
    });

    expect(event.item.serving_size_g).toBe(100);
    expect(event.item.serving_description).toBe('100g');
  });

  it('trims custom_unit whitespace', () => {
    const event = buildSaveEvent({
      name: 'Test',
      custom_unit: '  bottle  ',
      volume_ml: '',
      weight_g: '300',
      nutrients: { calories: 100 },
    });

    expect(event.custom_unit).toBe('bottle');
    expect(event.item.serving_description).toBe('1 bottle (300g)');
  });
});


describe('AddFoodView.handlePhotoSave → buildFoodPayload', () => {
  it('Type 1: weight-only produces correct API payload', () => {
    const event = buildSaveEvent({
      name: 'Oats',
      custom_unit: '',
      volume_ml: '',
      weight_g: '40',
      nutrients: { calories: 150, protein_g: 5, carbs_g: 27, fat_g: 2.5, fiber_g: 4 },
    });
    const payload = buildFoodPayload(event);

    expect(payload.name).toBe('Oats');
    expect(payload.serving_size).toBe(40);
    expect(payload.unit).toBe('g');
    expect(payload.gram_weight).toBe(40);
    expect(payload.calories).toBe(150);
    expect(payload.protein).toBe(5);
    expect(payload.carbs).toBe(27);
    expect(payload.fat).toBe(2.5);
    expect(payload.fiber).toBe(4);
    expect(payload.custom_unit).toBeUndefined();
    expect(payload.volume_ml).toBeUndefined();
  });

  it('Type 3: custom unit without volume', () => {
    const event = buildSaveEvent({
      name: 'Protein Bar',
      custom_unit: 'bar',
      volume_ml: '',
      weight_g: '60',
      nutrients: { calories: 200, protein_g: 20, carbs_g: 22, fat_g: 7, fiber_g: 3 },
    });
    const payload = buildFoodPayload(event);

    expect(payload.unit).toBe('bar');
    expect(payload.custom_unit).toBe('bar');
    expect(payload.volume_ml).toBeUndefined();
    expect(payload.serving_description).toBe('1 bar (60g)');
  });

  it('Type 4: custom unit with volume', () => {
    const event = buildSaveEvent({
      name: 'Shake',
      custom_unit: 'bottle',
      volume_ml: '325',
      weight_g: '325',
      nutrients: { calories: 140, protein_g: 30, carbs_g: 7, fat_g: 1.5, fiber_g: 4 },
    });
    const payload = buildFoodPayload(event);

    expect(payload.unit).toBe('bottle');
    expect(payload.custom_unit).toBe('bottle');
    expect(payload.volume_ml).toBe(325);
    expect(payload.serving_size).toBe(325);
    expect(payload.serving_description).toBe('1 bottle (325 mL, 325g)');
  });

  it('handles missing nutrients gracefully', () => {
    const event: PhotoSaveEvent = {
      item: {
        name: 'Sparse Food',
        serving_description: '100g',
        serving_size_g: 100,
        confidence: 'low',
        nutrients: {},  // completely empty
      },
      custom_unit: null,
      volume_ml: null,
    };
    const payload = buildFoodPayload(event);

    expect(payload.calories).toBe(0);
    expect(payload.protein).toBe(0);
    expect(payload.carbs).toBe(0);
    expect(payload.fat).toBe(0);
    expect(payload.fiber).toBe(0);
    expect(payload.name).toBe('Sparse Food');
  });

  it('handles null item name', () => {
    const event: PhotoSaveEvent = {
      item: {
        name: '',
        serving_description: '50g',
        serving_size_g: 50,
        confidence: 'low',
        nutrients: { calories: 10 },
      },
      custom_unit: null,
      volume_ml: null,
    };
    const payload = buildFoodPayload(event);
    expect(payload.name).toBe('Unknown Food');
  });

  it('handles zero serving_size_g', () => {
    const event: PhotoSaveEvent = {
      item: {
        name: 'Zero Weight',
        serving_description: '0g',
        serving_size_g: 0,
        confidence: 'low',
        nutrients: { calories: 50 },
      },
      custom_unit: null,
      volume_ml: null,
    };
    const payload = buildFoodPayload(event);
    expect(payload.serving_size).toBe(100); // fallback
  });

  it('JSON.stringify produces valid JSON with no NaN/undefined', () => {
    const event = buildSaveEvent({
      name: 'Test',
      custom_unit: 'can',
      volume_ml: '355',
      weight_g: '355',
      nutrients: { calories: NaN, protein_g: undefined as any, carbs_g: 0, fat_g: 0, fiber_g: 0 },
    });
    const payload = buildFoodPayload(event);
    const json = JSON.stringify(payload);

    expect(json).not.toContain('NaN');
    expect(json).not.toContain('undefined');
    expect(json).not.toContain('null');  // no null for required fields

    const parsed = JSON.parse(json);
    expect(parsed.name).toBe('Test');
    expect(parsed.calories).toBe(0);
    expect(parsed.protein).toBe(0);
    expect(typeof parsed.serving_size).toBe('number');
    expect(parsed.serving_size).toBeGreaterThan(0);
  });
});
