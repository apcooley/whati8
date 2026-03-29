import { describe, it, expect } from 'vitest';

/**
 * Tests for fraction parsing in quantity and volume fields.
 * 
 * Users should be able to enter fractions like "1/3", "1/4", "2/3"
 * and the system should convert them to decimal values.
 * 
 * The photo parser should also handle fraction-based serving descriptions
 * like "1/3 cup (80g)" correctly.
 */

// This is the function the app should use for parsing qty/volume inputs
function parseFraction(input: string): number | null {
  if (!input || !input.trim()) return null;
  const s = input.trim();

  // Try plain number first
  const plain = parseFloat(s);
  if (!isNaN(plain) && !/\//.test(s)) return plain;

  // Mixed number: "1 1/2" or "2 3/4"
  const mixedMatch = s.match(/^(\d+)\s+(\d+)\s*\/\s*(\d+)$/);
  if (mixedMatch) {
    const whole = parseInt(mixedMatch[1]);
    const num = parseInt(mixedMatch[2]);
    const den = parseInt(mixedMatch[3]);
    if (den === 0) return null;
    return whole + num / den;
  }

  // Simple fraction: "1/3", "3/4"
  const fracMatch = s.match(/^(\d+)\s*\/\s*(\d+)$/);
  if (fracMatch) {
    const num = parseInt(fracMatch[1]);
    const den = parseInt(fracMatch[2]);
    if (den === 0) return null;
    return num / den;
  }

  return null;
}


describe('parseFraction', () => {
  it('parses plain integers', () => {
    expect(parseFraction('4')).toBe(4);
    expect(parseFraction('1')).toBe(1);
    expect(parseFraction('12')).toBe(12);
  });

  it('parses plain decimals', () => {
    expect(parseFraction('0.5')).toBeCloseTo(0.5);
    expect(parseFraction('1.25')).toBeCloseTo(1.25);
    expect(parseFraction('0.333')).toBeCloseTo(0.333);
  });

  it('parses simple fractions', () => {
    expect(parseFraction('1/2')).toBeCloseTo(0.5);
    expect(parseFraction('1/3')).toBeCloseTo(0.333, 2);
    expect(parseFraction('1/4')).toBeCloseTo(0.25);
    expect(parseFraction('2/3')).toBeCloseTo(0.667, 2);
    expect(parseFraction('3/4')).toBeCloseTo(0.75);
  });

  it('parses fractions with spaces around slash', () => {
    expect(parseFraction('1 / 3')).toBeCloseTo(0.333, 2);
    expect(parseFraction('1 /4')).toBeCloseTo(0.25);
  });

  it('parses mixed numbers', () => {
    expect(parseFraction('1 1/2')).toBeCloseTo(1.5);
    expect(parseFraction('2 1/4')).toBeCloseTo(2.25);
    expect(parseFraction('1 2/3')).toBeCloseTo(1.667, 2);
  });

  it('returns null for empty or invalid', () => {
    expect(parseFraction('')).toBeNull();
    expect(parseFraction('abc')).toBeNull();
    expect(parseFraction('/')).toBeNull();
  });

  it('returns null for division by zero', () => {
    expect(parseFraction('1/0')).toBeNull();
  });
});


describe('Source code checks', () => {
  it('FoodEntryForm uses parseFraction, not raw parseFloat for qty', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/components/FoodEntryForm.svelte', 'utf-8');
    // Should use parseFraction for converting custom_qty
    expect(source).toContain('parseFraction');
  });

  it('FoodEntryForm qty input is type=text not type=number', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/components/FoodEntryForm.svelte', 'utf-8');
    // Qty per serving input should allow fractions (type=text, not type=number)
    // Look for the custom_qty input
    const qtyInputMatch = source.match(/custom_qty[\s\S]{0,200}type="(\w+)"/);
    expect(qtyInputMatch).toBeTruthy();
    expect(qtyInputMatch![1]).toBe('text');
  });

  it('FoodEntryForm volume_amount input is type=text not type=number', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/components/FoodEntryForm.svelte', 'utf-8');
    const volInputMatch = source.match(/volume_amount[\s\S]{0,200}type="(\w+)"/);
    expect(volInputMatch).toBeTruthy();
    expect(volInputMatch![1]).toBe('text');
  });

  it('FoodEntryForm qty regex matches fractions in serving descriptions', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/components/FoodEntryForm.svelte', 'utf-8');
    // The regex for parsing qty from serving description should handle "1/3 cup"
    // It should NOT be limited to just [\d.]+ which misses fractions
    expect(source).not.toMatch(/qtyMatch.*\[\\d\.\]\+/);
  });

  it('parseFraction utility exists in a shared location', async () => {
    const fs = await import('fs');
    // Should be importable from a utils file
    expect(
      fs.existsSync('src/lib/utils/parseFraction.ts') ||
      fs.existsSync('src/lib/utils.ts')
    ).toBe(true);
  });

  it('photo recognition prompt mentions fractions', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('../whati8/services/photo_recognition.py', 'utf-8');
    // Prompt should tell Claude to preserve fractions like "1/3 cup"
    expect(source.toLowerCase()).toContain('fraction');
  });
});
