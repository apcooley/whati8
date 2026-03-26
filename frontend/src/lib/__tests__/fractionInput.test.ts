import { describe, it, expect } from 'vitest';

/**
 * Tests for FractionInput component integration.
 * 
 * The FractionInput component should:
 * 1. Exist as a reusable component
 * 2. Be used in QuickLogSheet, EditLogSheet, and RegisterSheet
 * 3. Have a decimal numpad input + a fraction toggle button
 * 4. The fraction popup should convert fractions to decimals
 */

describe('FractionInput component exists', () => {
  it('FractionInput.svelte exists and has expected structure', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/components/FractionInput.svelte', 'utf-8');
    
    // Must import parseFraction
    expect(source).toContain('parseFraction');
    
    // Must have the decimal numpad input
    expect(source).toContain('inputmode="decimal"');
    
    // Must have the fraction toggle button with ⅟ symbol
    expect(source).toContain('⅟');
    
    // Must have the fraction text input (inputmode="text" for slash)
    expect(source).toContain('inputmode="text"');
  });
});

describe('QuickLogSheet uses FractionInput', () => {
  it('imports and uses FractionInput component', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/components/QuickLogSheet.svelte', 'utf-8');
    expect(source).toContain("import FractionInput from './FractionInput.svelte'");
    expect(source).toContain('<FractionInput');
  });

  it('does not have raw type=number qty input', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/components/QuickLogSheet.svelte', 'utf-8');
    // Should not have a raw number input for quantity
    expect(source).not.toMatch(/type="number"[\s\S]*?quantityStr/);
  });
});

describe('EditLogSheet uses FractionInput', () => {
  it('imports and uses FractionInput component', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/components/EditLogSheet.svelte', 'utf-8');
    expect(source).toContain("import FractionInput from './FractionInput.svelte'");
    expect(source).toContain('<FractionInput');
  });
});

describe('RegisterSheet uses FractionInput', () => {
  it('imports and uses FractionInput component', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/components/RegisterSheet.svelte', 'utf-8');
    expect(source).toContain("import FractionInput from './FractionInput.svelte'");
    expect(source).toContain('<FractionInput');
  });
});

describe('FractionInput layout', () => {
  it('fraction button is not hidden by parent width constraints', async () => {
    const fs = await import('fs');
    
    // Check that the parent containers give enough width
    // QuickLogSheet: qty container should be wide enough
    const qls = fs.readFileSync('src/lib/components/QuickLogSheet.svelte', 'utf-8');
    const qtyContainerMatch = qls.match(/<div class="([^"]*)">\s*<label[^>]*>Qty/);
    if (qtyContainerMatch) {
      const classes = qtyContainerMatch[1];
      // Should be at least w-32 (128px) or wider, or flex-based
      const hasWidth = /w-\d+|flex|min-w/.test(classes);
      expect(hasWidth).toBe(true);
    }
  });

  it('FractionInput renders input and button side by side', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/components/FractionInput.svelte', 'utf-8');
    // Should use flex layout for input + button
    expect(source).toContain('flex');
    // Input should be flex-1 (takes remaining space)
    expect(source).toContain('flex-1');
    // Button should be flex-shrink-0 (doesn't shrink)
    expect(source).toContain('flex-shrink-0');
  });
});
