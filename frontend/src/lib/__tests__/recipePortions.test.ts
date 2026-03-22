/**
 * Tests for recipe ingredient portion handling.
 * 
 * When a food is selected in RecipeIngredientRow, it fetches portions
 * from GET /foods/{id}/portions which returns:
 *   [{"description": "cup (240g)", "gram_weight": 240}, ...]
 * 
 * The component needs to:
 * 1. Parse this flat array into selectable portions
 * 2. Show ALL available portions (not just grams)
 * 3. Add grams and oz as fallbacks if not present
 * 4. Default quantity to 1 (not portion.amount)
 */

import { describe, it, expect } from 'vitest';

interface PortionApiResponse {
  description: string;
  gram_weight: number;
}

interface PortionOption {
  label: string;
  gram_weight: number;
  default_qty: number;
}

/**
 * Convert the API response into portion options for the dropdown.
 * This mirrors what RecipeIngredientRow should do.
 */
function parsePortionResponse(apiPortions: PortionApiResponse[]): PortionOption[] {
  const opts: PortionOption[] = [];
  
  for (const p of apiPortions) {
    // Skip NLEA servings
    if (p.description.toLowerCase().includes('nlea')) continue;
    // Skip "grams" and "oz" (we add them as fallbacks)
    if (p.description === 'grams' || p.description === 'oz') continue;
    
    opts.push({
      label: p.description,
      gram_weight: p.gram_weight,
      default_qty: 1,
    });
  }
  
  // Always add grams and oz
  if (!opts.some(o => o.label === 'grams')) {
    opts.push({ label: 'grams', gram_weight: 1, default_qty: 100 });
  }
  if (!opts.some(o => o.label === 'oz')) {
    opts.push({ label: 'oz', gram_weight: 28.35, default_qty: 1 });
  }
  
  return opts;
}


describe('parsePortionResponse', () => {
  it('USDA banana: returns all portion sizes', () => {
    const api: PortionApiResponse[] = [
      { description: 'extra large (9" or longer) (152.0g)', gram_weight: 152 },
      { description: 'large (8" to 8-7/8" long) (136.0g)', gram_weight: 136 },
      { description: 'cup, sliced (150.0g)', gram_weight: 150 },
      { description: 'small (6" to 6-7/8" long) (101.0g)', gram_weight: 101 },
      { description: 'medium (7" to 7-7/8" long) (118.0g)', gram_weight: 118 },
    ];
    const opts = parsePortionResponse(api);
    
    // Should have all 5 banana sizes + grams + oz = 7
    expect(opts.length).toBe(7);
    expect(opts.map(o => o.label)).toContain('cup, sliced (150.0g)');
    expect(opts.map(o => o.label)).toContain('grams');
    expect(opts.map(o => o.label)).toContain('oz');
  });

  it('custom food with custom unit: returns custom + grams + oz', () => {
    const api: PortionApiResponse[] = [
      { description: 'container (170g)', gram_weight: 170 },
      { description: 'grams', gram_weight: 1 },
      { description: 'oz', gram_weight: 28.35 },
    ];
    const opts = parsePortionResponse(api);
    
    expect(opts.length).toBe(3);
    expect(opts[0].label).toBe('container (170g)');
    expect(opts[0].gram_weight).toBe(170);
  });

  it('food with volume portions: includes cup, tbsp, etc.', () => {
    const api: PortionApiResponse[] = [
      { description: 'container (170g)', gram_weight: 170 },
      { description: 'cup (227g)', gram_weight: 227 },
      { description: 'tbsp (14g)', gram_weight: 14 },
      { description: 'tsp (5g)', gram_weight: 5 },
      { description: 'fl oz (28g)', gram_weight: 28 },
      { description: 'mL (1g)', gram_weight: 1 },
      { description: 'grams', gram_weight: 1 },
      { description: 'oz', gram_weight: 28.35 },
    ];
    const opts = parsePortionResponse(api);
    
    const labels = opts.map(o => o.label);
    expect(labels).toContain('cup (227g)');
    expect(labels).toContain('tbsp (14g)');
    expect(labels).toContain('container (170g)');
    // grams and oz added once (not duplicated)
    expect(labels.filter(l => l === 'grams').length).toBe(1);
    expect(labels.filter(l => l === 'oz').length).toBe(1);
  });

  it('skips NLEA serving', () => {
    const api: PortionApiResponse[] = [
      { description: 'NLEA serving (126g)', gram_weight: 126 },
      { description: 'medium (118g)', gram_weight: 118 },
    ];
    const opts = parsePortionResponse(api);
    expect(opts.map(o => o.label)).not.toContain('NLEA serving (126g)');
    expect(opts.map(o => o.label)).toContain('medium (118g)');
  });

  it('empty response: still has grams + oz', () => {
    const opts = parsePortionResponse([]);
    expect(opts.length).toBe(2);
    expect(opts.map(o => o.label)).toContain('grams');
    expect(opts.map(o => o.label)).toContain('oz');
  });

  it('default_qty is 1 for all portions', () => {
    const api: PortionApiResponse[] = [
      { description: 'cup (240g)', gram_weight: 240 },
    ];
    const opts = parsePortionResponse(api);
    const cup = opts.find(o => o.label === 'cup (240g)');
    expect(cup?.default_qty).toBe(1);
  });

  it('grams default_qty is 100', () => {
    const opts = parsePortionResponse([]);
    const g = opts.find(o => o.label === 'grams');
    expect(g?.default_qty).toBe(100);
  });
});
