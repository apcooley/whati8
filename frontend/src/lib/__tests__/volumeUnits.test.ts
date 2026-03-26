/**
 * Tests for volume unit handling in food creation.
 * 
 * Volume can apply to ANY food (yogurt, peanut butter, honey, etc.),
 * not just beverages. Users should be able to enter volume in any common unit.
 * 
 * Volume units and their mL equivalents:
 *   tsp = 4.929 mL
 *   tbsp = 14.787 mL
 *   fl oz = 29.5735 mL
 *   cup = 236.588 mL
 *   pint = 473.176 mL
 *   quart = 946.353 mL
 *   L = 1000 mL
 *   mL = 1 mL
 */

import { describe, it, expect } from 'vitest';

const VOLUME_TO_ML: Record<string, number> = {
  'tsp': 4.929,
  'tbsp': 14.787,
  'fl oz': 29.5735,
  'cup': 236.588,
  'pint': 473.176,
  'quart': 946.353,
  'L': 1000,
  'mL': 1,
};

/**
 * Convert a volume amount + unit to mL.
 */
function toMl(amount: number, unit: string): number {
  const factor = VOLUME_TO_ML[unit];
  if (!factor) throw new Error(`Unknown volume unit: ${unit}`);
  return amount * factor;
}

/**
 * Compute density from weight and volume.
 */
function computeDensity(weightG: number, volumeAmount: number, volumeUnit: string): number {
  const ml = toMl(volumeAmount, volumeUnit);
  return weightG / ml;
}

/**
 * Given density, compute gram_weight for each volume portion unit.
 */
function volumePortionWeights(density: number): Record<string, number> {
  const result: Record<string, number> = {};
  for (const [unit, mlPerUnit] of Object.entries(VOLUME_TO_ML)) {
    result[unit] = density * mlPerUnit;
  }
  return result;
}

/**
 * Build the payload for the backend from the photo form's volume fields.
 * The backend expects volume_ml (total volume in mL for the serving).
 */
function buildVolumePayload(
  volumeAmount: number | null, 
  volumeUnit: string | null
): number | null {
  if (!volumeAmount || !volumeUnit) return null;
  return toMl(volumeAmount, volumeUnit);
}


describe('toMl conversions', () => {
  it('1 cup = 236.588 mL', () => {
    expect(toMl(1, 'cup')).toBeCloseTo(236.588, 1);
  });

  it('1 tbsp = 14.787 mL', () => {
    expect(toMl(1, 'tbsp')).toBeCloseTo(14.787, 1);
  });

  it('1 fl oz = 29.5735 mL', () => {
    expect(toMl(1, 'fl oz')).toBeCloseTo(29.574, 1);
  });

  it('0.75 cup (3/4 cup) = 177.4 mL', () => {
    expect(toMl(0.75, 'cup')).toBeCloseTo(177.4, 0);
  });

  it('2 tbsp = 29.574 mL', () => {
    expect(toMl(2, 'tbsp')).toBeCloseTo(29.574, 0);
  });

  it('500 mL = 500 mL', () => {
    expect(toMl(500, 'mL')).toBe(500);
  });

  it('1 L = 1000 mL', () => {
    expect(toMl(1, 'L')).toBe(1000);
  });

  it('unknown unit throws', () => {
    expect(() => toMl(1, 'gallon')).toThrow('Unknown volume unit');
  });
});


describe('density calculations', () => {
  it('yogurt: 170g in 3/4 cup → density ~0.96 g/mL', () => {
    const d = computeDensity(170, 0.75, 'cup');
    expect(d).toBeCloseTo(0.958, 2);
  });

  it('honey: 21g in 1 tbsp → density ~1.42 g/mL', () => {
    const d = computeDensity(21, 1, 'tbsp');
    expect(d).toBeCloseTo(1.42, 1);
  });

  it('peanut butter: 32g in 2 tbsp → density ~1.08 g/mL', () => {
    const d = computeDensity(32, 2, 'tbsp');
    expect(d).toBeCloseTo(1.08, 1);
  });

  it('water: 236g in 1 cup → density ~1.0 g/mL', () => {
    const d = computeDensity(236, 1, 'cup');
    expect(d).toBeCloseTo(1.0, 1);
  });

  it('milk: 244g in 1 cup → density ~1.03 g/mL', () => {
    const d = computeDensity(244, 1, 'cup');
    expect(d).toBeCloseTo(1.03, 1);
  });
});


describe('volumePortionWeights', () => {
  it('yogurt density 0.958: 1 cup = 226.6g', () => {
    const weights = volumePortionWeights(0.958);
    expect(weights['cup']).toBeCloseTo(226.7, 0);
  });

  it('yogurt density 0.958: 1 tbsp = 14.2g', () => {
    const weights = volumePortionWeights(0.958);
    expect(weights['tbsp']).toBeCloseTo(14.2, 0);
  });

  it('yogurt density 0.958: 1 fl oz = 28.3g', () => {
    const weights = volumePortionWeights(0.958);
    expect(weights['fl oz']).toBeCloseTo(28.3, 0);
  });

  it('honey density 1.42: 1 tbsp = 21g', () => {
    const weights = volumePortionWeights(1.42);
    expect(weights['tbsp']).toBeCloseTo(21.0, 0);
  });

  it('all units present in output', () => {
    const weights = volumePortionWeights(1.0);
    expect(Object.keys(weights)).toEqual(
      expect.arrayContaining(['tsp', 'tbsp', 'fl oz', 'cup', 'pint', 'quart', 'L', 'mL'])
    );
  });
});


describe('buildVolumePayload', () => {
  it('3/4 cup → 177.4 mL', () => {
    const ml = buildVolumePayload(0.75, 'cup');
    expect(ml).toBeCloseTo(177.4, 0);
  });

  it('2 tbsp → 29.6 mL', () => {
    const ml = buildVolumePayload(2, 'tbsp');
    expect(ml).toBeCloseTo(29.6, 0);
  });

  it('11 fl oz → 325.3 mL', () => {
    const ml = buildVolumePayload(11, 'fl oz');
    expect(ml).toBeCloseTo(325.3, 0);
  });

  it('null amount → null', () => {
    expect(buildVolumePayload(null, 'cup')).toBeNull();
  });

  it('null unit → null', () => {
    expect(buildVolumePayload(0.75, null)).toBeNull();
  });

  it('zero amount → null', () => {
    expect(buildVolumePayload(0, 'cup')).toBeNull();
  });
});


describe('backend portion creation with volume', () => {
  it('yogurt 170g, 3/4 cup: backend gets volume_ml=177.4', () => {
    const ml = buildVolumePayload(0.75, 'cup')!;
    // Backend computes: density = 170 / 177.4 = 0.958
    const density = 170 / ml;
    expect(density).toBeCloseTo(0.958, 2);
    
    // Portions created by backend:
    // fl oz = 0.958 * 29.5735 = 28.3g
    expect(density * 29.5735).toBeCloseTo(28.3, 0);
    // mL = 0.958g
    expect(density * 1).toBeCloseTo(0.958, 2);
    // cup = 0.958 * 236.588 = 226.7g  
    expect(density * 236.588).toBeCloseTo(226.7, 0);
    // tbsp = 0.958 * 14.787 = 14.2g
    expect(density * 14.787).toBeCloseTo(14.2, 0);
    // tsp = 0.958 * 4.929 = 4.7g
    expect(density * 4.929).toBeCloseTo(4.7, 0);
  });
});
