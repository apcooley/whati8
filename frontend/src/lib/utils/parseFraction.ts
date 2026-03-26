export function parseFraction(input: string): number | null {
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
