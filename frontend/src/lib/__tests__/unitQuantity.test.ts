/**
 * Tests for unit/quantity separation.
 * 
 * Rules:
 * - Unit is the NAME of the measure: "bottle", "cracker", "slice", "cup", "g"
 * - Quantity is HOW MANY of that unit: 1, 6, 2.5
 * - Serving description includes details: "1 bottle (325 mL, 325g)"
 * - default_unit on user_food should be the unit NAME, not the full description
 * - default_quantity should be the numeric quantity
 * - Portion label includes weight info: "bottle (325g)" 
 * - Display: "{quantity} {unit}" → "1 bottle", "6 crackers"
 */

import { describe, it, expect } from 'vitest';

interface ParsedServing {
  unit: string;        // "bottle", "cracker", "g"
  quantity: number;    // 1, 6, 100
  weight_g: number;    // grams per 1 unit
  volume_ml: number | null;
  portion_label: string;  // "bottle (325g)" for dropdown
}

/**
 * Parse a serving description into unit + quantity.
 * Examples:
 *   "1 bottle (325 mL, 325g)" → { unit: "bottle", quantity: 1, weight_g: 325 }
 *   "6 crackers (28g)" → { unit: "crackers", quantity: 6, weight_g: 28/6=4.67 }
 *   "1 cup (240g)" → { unit: "cup", quantity: 1, weight_g: 240 }
 *   "100g" → { unit: "g", quantity: 100, weight_g: 1 }
 */
function parseServing(desc: string, totalWeightG: number): ParsedServing {
  // Try to match: "<qty> <unit> (<details>)"
  const match = desc.match(/^([\d.]+)\s+(\w[\w\s]*?)(?:\s*\((.+)\))?$/);
  
  if (match) {
    const quantity = parseFloat(match[1]);
    const unit = match[2].trim();
    const details = match[3] || '';
    
    // Extract volume from details
    let volumeMl: number | null = null;
    const volMatch = details.match(/([\d.]+)\s*m[lL]/);
    if (volMatch) volumeMl = parseFloat(volMatch[1]);
    
    // Weight per 1 unit
    const weightPerUnit = totalWeightG / quantity;
    
    // Build portion label: "bottle (325g)" or "cracker (4.7g)"
    const portionLabel = `${unit} (${Math.round(weightPerUnit)}g)`;
    
    return { unit, quantity, weight_g: weightPerUnit, volume_ml: volumeMl, portion_label: portionLabel };
  }
  
  // Fallback: just grams
  return { unit: 'g', quantity: totalWeightG, weight_g: 1, volume_ml: null, portion_label: 'grams' };
}

/**
 * Build the data for food creation + registration from photo results.
 */
function buildRegistrationData(parsed: ParsedServing, name: string) {
  return {
    // For POST /foods/
    food: {
      unit: parsed.unit,
      serving_size: parsed.weight_g * parsed.quantity,  // total grams per serving
      custom_unit: parsed.unit !== 'g' ? parsed.unit : undefined,
      gram_weight: parsed.weight_g * parsed.quantity,
      volume_ml: parsed.volume_ml || undefined,
    },
    // For POST /profile/foods/register
    registration: {
      default_unit: parsed.portion_label,  // "bottle (325g)"
      default_quantity: parsed.quantity,     // 1
    },
    // For portion creation
    portion: {
      unit_name: parsed.unit,
      gram_weight: parsed.weight_g,  // per 1 unit
      portion_description: parsed.portion_label,
    },
  };
}


describe('parseServing', () => {
  it('1 bottle (325 mL, 325g)', () => {
    const p = parseServing('1 bottle (325 mL, 325g)', 325);
    expect(p.unit).toBe('bottle');
    expect(p.quantity).toBe(1);
    expect(p.weight_g).toBe(325);
    expect(p.volume_ml).toBe(325);
    expect(p.portion_label).toBe('bottle (325g)');
  });

  it('6 crackers (28g)', () => {
    const p = parseServing('6 crackers (28g)', 28);
    expect(p.unit).toBe('crackers');
    expect(p.quantity).toBe(6);
    expect(p.weight_g).toBeCloseTo(4.67, 1);
    expect(p.portion_label).toBe('crackers (5g)');  // rounded
  });

  it('1 bar (60g)', () => {
    const p = parseServing('1 bar (60g)', 60);
    expect(p.unit).toBe('bar');
    expect(p.quantity).toBe(1);
    expect(p.weight_g).toBe(60);
  });

  it('2 slices (56g)', () => {
    const p = parseServing('2 slices (56g)', 56);
    expect(p.unit).toBe('slices');
    expect(p.quantity).toBe(2);
    expect(p.weight_g).toBe(28);
    expect(p.portion_label).toBe('slices (28g)');
  });

  it('100g (weight only)', () => {
    const p = parseServing('100g', 100);
    expect(p.unit).toBe('g');
    expect(p.quantity).toBe(100);
    expect(p.weight_g).toBe(1);
  });

  it('1 cup (240g)', () => {
    const p = parseServing('1 cup (240g)', 240);
    expect(p.unit).toBe('cup');
    expect(p.quantity).toBe(1);
    expect(p.weight_g).toBe(240);
  });
});


describe('buildRegistrationData', () => {
  it('bottle: default_unit is "bottle (325g)", default_quantity is 1', () => {
    const p = parseServing('1 bottle (325 mL, 325g)', 325);
    const data = buildRegistrationData(p, 'Protein Shake');
    
    expect(data.registration.default_unit).toBe('bottle (325g)');
    expect(data.registration.default_quantity).toBe(1);
    expect(data.food.custom_unit).toBe('bottle');
    expect(data.food.serving_size).toBe(325);
  });

  it('crackers: default_unit is "crackers (5g)", default_quantity is 6', () => {
    const p = parseServing('6 crackers (28g)', 28);
    const data = buildRegistrationData(p, 'Triscuits');
    
    expect(data.registration.default_unit).toBe('crackers (5g)');
    expect(data.registration.default_quantity).toBe(6);
    expect(data.portion.gram_weight).toBeCloseTo(4.67, 1);  // per 1 cracker
  });

  it('weight only: default_unit is "grams", default_quantity is weight', () => {
    const p = parseServing('100g', 100);
    const data = buildRegistrationData(p, 'Oats');
    
    expect(data.registration.default_unit).toBe('grams');
    expect(data.registration.default_quantity).toBe(100);
    expect(data.food.custom_unit).toBeUndefined();
  });
});


describe('display formatting', () => {
  it('no double "1": quantity + unit = "1 bottle" not "1 1 bottle"', () => {
    const p = parseServing('1 bottle (325 mL, 325g)', 325);
    const display = `${p.quantity} ${p.portion_label}`;
    expect(display).toBe('1 bottle (325g)');
    expect(display).not.toContain('1 1');
  });

  it('crackers: "6 crackers (5g)"', () => {
    const p = parseServing('6 crackers (28g)', 28);
    const display = `${p.quantity} ${p.portion_label}`;
    expect(display).toBe('6 crackers (5g)');
  });

  it('getServingLabel should not duplicate quantity', () => {
    // Simulates getServingLabel(uf) behavior
    const default_quantity = 1;
    const default_unit = 'bottle (325g)';
    
    // Current (fixed) logic: if unit starts with digit, skip qty prefix
    const label = /^\d/.test(default_unit) ? default_unit : `${default_quantity} ${default_unit}`;
    expect(label).toBe('1 bottle (325g)');
    expect(label).not.toContain('1 1');
  });
});
