# Bug Fix: Duplicate Quantity in Food Display

## Problem

Food items in whati8 were displaying duplicated quantities:
- Built Puff bars showed "**1 1 Bar (44g)**" instead of "**1 Bar (44g)**"
- Crackers showed "**6 6 crackers (28g)**" instead of "**6 crackers (28g)**"
- Grams showed "**1 113g**" instead of "**113g**"

## Root Cause

The `getServingLabel()` function in `frontend/src/lib/types/profile.ts` was blindly concatenating `default_quantity` and `default_unit`:

```typescript
// BEFORE (buggy):
export function getServingLabel(uf: UserFood): string {
  const qty = uf.default_quantity ?? uf.food.serving_size;
  const unit = uf.default_unit ?? uf.food.unit;
  return `${qty} ${unit}`;  // ❌ Always prepends quantity
}
```

However, the `default_unit` field in the database already contained the quantity prefix in many cases:

| default_quantity | default_unit        | Result (buggy)          | Expected           |
|------------------|---------------------|-------------------------|--------------------|
| 1.0              | "1 Bar (44g)"       | "1 1 Bar (44g)" ❌       | "1 Bar (44g)"      |
| 6.0              | "6 crackers (28g)"  | "6 6 crackers (28g)" ❌  | "6 crackers (28g)" |
| 1.0              | "113g"              | "1 113g" ❌              | "113g"             |
| 1.0              | "bottle (325g)"     | "1 bottle (325g)" ✅     | "1 bottle (325g)"  |

## Solution

Updated `getServingLabel()` to detect when `default_unit` already starts with a digit and skip prepending the quantity:

```typescript
// AFTER (fixed):
export function getServingLabel(uf: UserFood): string {
  const qty = uf.default_quantity ?? uf.food.serving_size;
  const unit = uf.default_unit ?? uf.food.unit;
  
  // If unit starts with a digit, it already includes quantity
  // Examples: "1 Bar (44g)", "6 crackers (28g)", "113g"
  if (unit && /^\d/.test(unit)) {
    return unit;
  }
  
  // Format quantity: remove .0 for whole numbers
  const qtyStr = Number.isInteger(qty) ? String(Math.round(qty)) : String(qty);
  
  // Otherwise prepend quantity
  return `${qtyStr} ${unit}`;
}
```

## Changes Made

### 1. Fixed Implementation
- **File**: `frontend/src/lib/types/profile.ts`
- **Function**: `getServingLabel()`
- **Logic**: Detect digit-prefixed units and avoid duplication
- **Bonus**: Format whole numbers without `.0` suffix (e.g., "1" instead of "1.0")

### 2. Comprehensive Tests
- **File**: `tests/test_duplicate_qty_bug.py`
- **Coverage**: 25 test cases including:
  - Bars with quantity prefix
  - Crackers with quantity prefix
  - Grams-only format
  - Units without quantity prefix
  - Edge cases (empty unit, zero quantity, decimal quantities)
  - Real-world patterns from production database

### 3. Test Results
```bash
$ uv run pytest tests/test_duplicate_qty_bug.py -v
========================= 25 passed, 1 warning in 0.02s =========================
```

### 4. Build Verification
```bash
$ cd frontend && npm run build
✓ built in 1.45s
```

No TypeScript errors, build successful.

## Examples

### Before Fix
```
1 1 Bar (44g)        ❌
6 6 crackers (28g)   ❌
1 113g               ❌
1.0 bottle (325g)    ❌ (unnecessary .0)
```

### After Fix
```
1 Bar (44g)          ✅
6 crackers (28g)     ✅
113g                 ✅
1 bottle (325g)      ✅
```

## Database Patterns Observed

From `user_foods` table:

| default_quantity | default_unit        | Pattern Type            |
|------------------|---------------------|-------------------------|
| 1.0              | "1 Bar (44g)"       | Quantity prefix         |
| 6.0              | "6 crackers (28g)"  | Quantity prefix         |
| 1.0              | "113g"              | Weight only             |
| 1.0              | "32g"               | Weight only             |
| 1.0              | "bottle (325g)"     | Unit only               |
| 1.0              | "roll (43g)"        | Unit only               |
| 4.0              | "slices (14g)"      | Unit only               |
| 100.0            | "grams"             | Unit only (plain text)  |
| 1.0              | "1 Bun (43g)"       | Quantity prefix         |

## Future Considerations

### Data Consistency
The `default_unit` field has inconsistent formats. Consider:
1. **Normalize on write**: Strip quantity prefix when saving `default_unit`
2. **Store separately**: Keep quantity and unit in separate fields
3. **Migration**: Clean up existing data for consistency

### Current Workaround
The fix handles both patterns gracefully without requiring data migration:
- ✅ Works with quantity-prefixed units (legacy data)
- ✅ Works with clean unit-only values (new format)
- ✅ Formats quantities cleanly (no unnecessary decimals)

## Verification Steps

1. ✅ Run tests: `uv run pytest tests/test_duplicate_qty_bug.py -v`
2. ✅ Build frontend: `cd frontend && npm run build`
3. ⏳ Visual verification: Start app and check "Log Food" page
4. ⏳ Screenshot comparison: Before/after screenshots

## Files Modified

1. `frontend/src/lib/types/profile.ts` - Fixed `getServingLabel()`
2. `tests/test_duplicate_qty_bug.py` - Added comprehensive test suite
3. `BUG_FIX_DUPLICATE_QUANTITY.md` - This documentation

---

**Status**: ✅ Tests passing, build successful
**Next**: Visual verification in running app
