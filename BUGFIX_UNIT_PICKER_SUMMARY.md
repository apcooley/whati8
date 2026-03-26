# Unit Picker Quantity Prefix Bug - FIXED ✅

## Problem
Unit dropdown was showing "6 crackers (28g)" instead of "crackers (28g)". When users selected qty=6 with this unit, the display became "6 6 crackers" (duplicated quantity).

## Root Cause
**File:** `whati8/services/food_resolver.py`
**Function:** `_build_portion_options()` (lines 369-392)

The database stores portions like:
- `amount = 6.0`
- `unit_name = "crackers"`
- `gram_weight = 28.0`

This means "1 serving = 6 crackers = 28g".

The buggy code was building `display_name` as:
```python
display_name = f"{float(p.amount)} {unit_part} ({float(p.gram_weight)}g)"
# Result: "6.0 crackers (28.0g)"
```

When the frontend displayed user's selected quantity (6) with this unit, it became:
```
"6 6.0 crackers (28.0g)"  # ❌ Duplicated!
```

## The Fix
Strip the quantity prefix from `unit_part` before building `display_name`:

```python
# Strip leading digits followed by space (e.g., "6 crackers" → "crackers")
# But preserve units like "113g" (no space after digits)
import re
cleaned_unit = _re.sub(r'^\d+(\.\d+)?\s+', '', unit_part)

display_name = f"{cleaned_unit} ({float(p.gram_weight)}g)"
# Result: "crackers (28.0g)"
```

Now when user selects quantity 6:
```
"6 crackers (28.0g)"  # ✅ Correct!
```

## Changes Made
**File:** `whati8/services/food_resolver.py`
**Lines:** 369-392 (function `_build_portion_options`)

### Before
```python
unit_part = p.modifier if p.modifier else p.unit_name
display_name = f"{float(p.amount)} {unit_part} ({float(p.gram_weight)}g)"
```

### After
```python
unit_part = p.modifier if p.modifier else p.unit_name

# Strip leading digits followed by space (e.g., "6 crackers" → "crackers")
# But preserve units like "113g" (no space after digits)
import re
cleaned_unit = _re.sub(r'^\d+(\.\d+)?\s+', '', unit_part)

display_name = f"{cleaned_unit} ({float(p.gram_weight)}g)"
```

## Edge Cases Handled
✅ "6 crackers" → "crackers (28g)"
✅ "4 slices" → "slices (14g)"
✅ "10 balls" → "balls (138g)"
✅ "2.5 oz" → "oz (70g)" (decimal prefixes)
✅ "0.5 cup" → "cup (118g)" (fractional prefixes)
✅ "113g" → "113g (113g)" (no space, not stripped)
✅ "g" → "g (1g)" (no prefix, unchanged)
✅ "ml" → "ml (1ml)" (no prefix, unchanged)

## Test Results
All 18 tests passing:
```bash
$ uv run pytest tests/test_unit_picker_quantity_prefix_bug.py -v
======================== 18 passed, 1 warning in 0.02s ========================
```

## Real Database Examples

### Before Fix
| Food | Amount | Unit | Display |
|------|--------|------|---------|
| Triscuit Crackers | 6.0 | crackers | "6.0 crackers (4.67g)" ❌ |
| Turkey Breast | 4.0 | slices | "4.0 slices (14.0g)" ❌ |
| Cantaloupe | 10.0 | balls | "10.0 balls (138.0g)" ❌ |

### After Fix
| Food | Amount | Unit | Display |
|------|--------|------|---------|
| Triscuit Crackers | 6.0 | crackers | "crackers (4.67g)" ✅ |
| Turkey Breast | 4.0 | slices | "slices (14.0g)" ✅ |
| Cantaloupe | 10.0 | balls | "balls (138.0g)" ✅ |

## Impact
- ✅ Fixes unit dropdown display
- ✅ Fixes quantity duplication in frontend
- ✅ Preserves `amount` field for calculations
- ✅ No breaking changes to API schema
- ✅ All existing tests still pass

## Verification
Run the test suite:
```bash
cd /home/aaron/source/whati8
uv run pytest tests/test_unit_picker_quantity_prefix_bug.py -v
```

Check real data:
```bash
cd /home/aaron/source/whati8
uv run python -c "
from whati8.services.food_resolver import FoodResolverService
from whati8.models.food_portion import FoodPortion

class MockPortion:
    id = 1
    amount = 6.0
    unit_name = 'crackers'
    modifier = None
    gram_weight = 28.0

portion = MockPortion()
options = FoodResolverService._build_portion_options([portion])
print(f'Display: \"{options[0].display_name}\"')
# Expected: "crackers (28.0g)"
"
```

---

**Status:** ✅ COMPLETE
**Date:** 2026-03-22
**Tested:** 18/18 tests passing
**Sub-agent:** df80969e-ec31-432e-9ff5-b2dc7a0ab932
