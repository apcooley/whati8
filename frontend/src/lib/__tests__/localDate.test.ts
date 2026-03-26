import { describe, it, expect } from 'vitest';

/**
 * Tests for local date handling in the frontend.
 * 
 * The app must use the user's local date, not UTC, for:
 * 1. "Today" calculation in dailyLogs store
 * 2. "Is today" check in DayNavigator
 * 3. Date navigation (prev/next day arrows)
 */

// Helper that mimics what the code should use
function localDateStr(d: Date = new Date()): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

describe('Local date vs UTC', () => {
  it('localDateStr returns local date, not UTC', () => {
    // March 22, 2026 at 11:30 PM MDT = March 23, 2026 at 05:30 UTC
    // Create a date that's late at night in a negative-UTC-offset timezone
    const d = new Date(2026, 2, 22, 23, 30, 0); // month is 0-indexed, so 2 = March
    const result = localDateStr(d);
    expect(result).toBe('2026-03-22');
    // The bug: toISOString().slice(0,10) would give '2026-03-23' if UTC offset pushes past midnight
  });

  it('toISOString gives UTC date which can differ from local', () => {
    // This documents the bug we're fixing
    const d = new Date(2026, 2, 22, 23, 30, 0);
    const isoDate = d.toISOString().slice(0, 10);
    const localDate = localDateStr(d);
    // In UTC-negative timezones (Americas), late night local = next day UTC
    // This test passes in any timezone, documenting the concept
    expect(localDate).toBe('2026-03-22');
    // isoDate could be '2026-03-22' or '2026-03-23' depending on test runner timezone
    // The key point: localDate is always the wall-clock date
  });

  it('localDateStr pads single-digit months and days', () => {
    const d = new Date(2026, 0, 5); // Jan 5
    expect(localDateStr(d)).toBe('2026-01-05');
  });

  it('date arithmetic stays local', () => {
    // Simulates the prev/next day navigation
    const d = new Date('2026-03-22T12:00:00'); // noon local
    d.setDate(d.getDate() + 1);
    const result = localDateStr(d);
    expect(result).toBe('2026-03-23');
  });

  it('date arithmetic backwards stays local', () => {
    const d = new Date('2026-03-22T12:00:00');
    d.setDate(d.getDate() - 1);
    expect(localDateStr(d)).toBe('2026-03-21');
  });
});

describe('Source code checks', () => {
  it('dailyLogs store does not use toISOString for today', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/stores/dailyLogs.ts', 'utf-8');
    expect(source).not.toContain('toISOString');
  });

  it('DayNavigator does not use toISOString', async () => {
    const fs = await import('fs');
    const source = fs.readFileSync('src/lib/components/DayNavigator.svelte', 'utf-8');
    expect(source).not.toContain('toISOString');
  });
});
