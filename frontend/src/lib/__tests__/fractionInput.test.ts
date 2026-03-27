import { describe, it, expect } from 'vitest';

/**
 * Tests for FractionInput component integration.
 * 
 * The FractionInput component should:
 * 1. Exist as a reusable component with decimal/fraction toggle
 * 2. Be used in QuickLogSheet, EditLogSheet, and RegisterSheet
 * 3. Have inputmode switching between decimal and text
 * 4. Import parseFraction for conversion
 */

describe('FractionInput component exists', () => {
  it('FractionInput.svelte exists and has expected structure', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/components/FractionInput.svelte', 'utf-8');
    
    // Must import parseFraction
    expect(source).toContain('parseFraction');
    
    // Must have decimal inputmode for number pad
    expect(source).toContain('inputmode');
    expect(source).toContain('decimal');
    
    // Must have text inputmode for fraction entry
    expect(source).toContain('text');
    
    // Must have the toggle labels
    expect(source).toContain('0.5');
    expect(source).toContain('1/2');
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
  it('parent containers give enough width for qty input', async () => {
    const fs = await import('fs');
    const qls = fs.readFileSync('src/lib/components/QuickLogSheet.svelte', 'utf-8');
    const qtyContainerMatch = qls.match(/<div class="([^"]*)">\s*<label[^>]*>Qty/);
    if (qtyContainerMatch) {
      const classes = qtyContainerMatch[1];
      const hasWidth = /w-\d+|flex|min-w/.test(classes);
      expect(hasWidth).toBe(true);
    }
  });

  it('FractionInput has mode toggle', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/components/FractionInput.svelte', 'utf-8');
    // Should have fractionMode toggle state
    expect(source).toContain('fractionMode');
    // Should have toggle buttons
    expect(source).toMatch(/button.*type="button"/);
  });
});
