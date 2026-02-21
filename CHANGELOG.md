# whati8 Changelog

## 2026-02-09 - Multi-Food UI, Search Improvements, Unit Handling

### Features
- **Multi-food confirmation UI** - Review, edit, and batch-submit multiple parsed food items
- **USDA data import complete** - 8,058 foods, 260 nutrients, 14,574 household portions
- **Household portion matching** - "1 cup", "1 large egg", etc. converted to grams
- **Multi-term search** - AI generates search variations for better USDA matching
- **Smart unit dropdown** - Only shows units that make sense for each food

### Improvements
- Search prefers foods WITH portions when similarity scores tie
- Portions included in search results and alternatives
- Volume detection checks both `modifier` and `unit_name` fields
- Agent suppresses verbose output when showing confirmation form

### Bug Fixes
- Fixed duplicate index on `FoodPortion.food_id`
- Fixed `crypto.randomUUID` fallback for older browsers
- Fixed "254undefined" unit display bug
- Fixed A11y warnings across 5 frontend components
- Replaced deprecated `@app.on_event("startup")` with lifespan context manager
- Added pg_trgm extension creation in test fixtures

### Files Modified
**Backend:**
- `whati8/services/food_resolver.py` - Multi-term search, portion matching, search_terms
- `whati8/services/agent_service.py` - Suppress verbose form messages
- `whati8/schemas/food_resolver.py` - ParsedFoodItem.search_terms, PortionOption
- `whati8/schemas/food.py` - PortionItem, portions in search results
- `whati8/api/routers/food.py` - Portions in search, secondary sort
- `whati8/api/app.py` - Lifespan context manager
- `whati8/models/food_portion.py` - Removed duplicate index
- `tests/conftest.py` - pg_trgm extension

**Frontend:**
- `QuantityEditor.svelte` - Smart unit list, proper conversions
- `FoodSelector.svelte` - Portions type, unit display fix
- `FoodRow.svelte` - Pass portions through search/select
- `FormModal.svelte` - A11y fixes
- `MultiFoodForm.svelte` - A11y fixes
- `MealSelector.svelte` - A11y fixes
- `InlineAddFood.svelte` - crypto.randomUUID fallback

### Test Results
- 86 backend tests passing
- 0 frontend warnings

### Known Limitations
- Some USDA foods have 0 portions (data gap)
- No branded foods (Pure Protein, etc.) - need Custom Foods or Open Food Facts
- Trigram fuzzy search can match poorly for some queries

---

## Next Up
- **Custom Foods UI** - See `CUSTOM_FOODS_PLAN.md`
- **Open Food Facts integration** - Branded products
- **WW Points tracking**
