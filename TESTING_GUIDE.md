# Copy/Move UI Testing Guide

## Quick Start

The copy/move UI is now live! Access it at: http://localhost:8000

## Features to Test

### 1. Individual Log Copy/Move

**Location:** Daily logs view, any log entry

**Steps:**
1. Navigate to Daily Logs tab
2. Find any logged food item
3. Click the **⋮** (vertical dots) menu button on the right
4. Menu appears with 4 options:
   - ✏️ Edit
   - 📋 Copy to...
   - ↗️ Move to...
   - 🗑️ Delete

**Test Copy:**
1. Click "📋 Copy to..."
2. Sheet opens titled "Copy log to..."
3. Date defaults to today
4. Meal selector shows 4 meals (defaults to original)
5. Change date/meal as desired
6. Click "Copy" button
7. Toast appears: "Log copied"
8. Navigate to target date to verify log appears
9. Navigate back to original date to verify log still exists

**Test Move:**
1. Click "↗️ Move to..."
2. Sheet opens titled "Move log to..."
3. Same interface as copy
4. Click "Move" button
5. Toast appears: "Log moved"
6. Original log disappears from current view
7. Navigate to target date to verify log appears there

### 2. Meal-Level Copy

**Location:** Daily logs view, meal group headers

**Steps:**
1. Navigate to Daily Logs tab
2. Look for meal headers (BREAKFAST, LUNCH, DINNER, SNACK)
3. If meal has logs, you'll see "📋 Copy" button next to calorie total
4. Click "📋 Copy" button
5. Sheet opens titled "Copy meal to..."
6. Shows meal name and item count (e.g., "Lunch (3 items)")
7. Date picker defaults to today
8. Target meal selector (defaults to same meal, e.g., Lunch → Lunch)
9. Change date/meal if desired
10. Click "Copy Meal" button
11. Toast appears: "Lunch copied" (or other meal name)
12. Navigate to target date to verify all logs copied

### 3. UI/UX Details

**Menu Behavior:**
- Click ⋮ button to open menu
- Click away from menu to close
- Press Escape key to close
- Selecting any option closes menu
- Menu positioned to not overflow screen

**Sheet Behavior:**
- Click backdrop to close (dark overlay)
- Press Escape key to close
- Click "Cancel" button to close
- Successful operations auto-close sheet

**Date Picker:**
- Native browser date picker
- Defaults to today's date
- Can select past or future dates
- Proper format: YYYY-MM-DD

**Meal Selector:**
- 4 buttons: Breakfast, Lunch, Dinner, Snack
- Click to select (blue highlight)
- Click again to deselect (returns to null = use original)
- Multiple clicks toggle selection on/off

**Toast Notifications:**
- Success: "Log copied" / "Log moved" / "{Meal} copied"
- Error: Shows API error message if operation fails

### 4. Edge Cases to Test

- [ ] Copy log to same date (should work, creates duplicate)
- [ ] Move log to same date but different meal (only meal changes)
- [ ] Copy empty meal (button shouldn't appear)
- [ ] Copy meal with 1 item vs. many items
- [ ] Copy to past dates
- [ ] Copy to far future dates
- [ ] Cancel operations (verify no changes)
- [ ] Rapid clicks (verify no duplicate operations)
- [ ] Network error handling (kill server, try operation)

### 5. Mobile-Specific Testing

If testing on mobile device:
- [ ] Touch targets are large enough (44px minimum)
- [ ] Menu doesn't require precise tap
- [ ] Date picker shows native iOS/Android picker
- [ ] Sheets slide up smoothly from bottom
- [ ] Backdrop tap closes sheet
- [ ] Keyboard doesn't obscure inputs
- [ ] Safe area respected (no content behind home indicator)

### 6. Verify Data Integrity

After copy/move operations:
- [ ] All nutrients preserved (calories, protein, carbs, fat, fiber)
- [ ] Quantity and unit preserved
- [ ] Food name unchanged
- [ ] Notes preserved (if any)
- [ ] Move removes from source completely
- [ ] Copy leaves source unchanged

### 7. Backend Tests

Already verified (27/27 passing):
```bash
cd /home/aaron/source/whati8
uv run python -m pytest tests/test_copy_move_logs.py -v
```

All backend endpoints working correctly:
- ✅ Copy single log
- ✅ Move single log  
- ✅ Copy entire meal
- ✅ Error handling (404s, validation)
- ✅ User isolation (can't copy other users' logs)

### 8. Known Limitations

- No undo for move operations (would require backend changes)
- Can't select multiple logs to batch copy/move
- No drag-and-drop support yet
- No keyboard shortcuts

### 9. If Something Breaks

**Check server logs:**
```bash
tail -f /tmp/whati8_server.log
```

**Restart server:**
```bash
pkill -f "whati8 serve"
cd /home/aaron/source/whati8
uv run python -m whati8 serve --reload
```

**Rebuild frontend:**
```bash
cd /home/aaron/source/whati8/frontend
npx vite build
```

**Check database:**
```bash
cd /home/aaron/source/whati8
uv run python -c "
from whati8.api.database import get_db
from sqlalchemy import text
db = next(get_db())
result = db.execute(text('SELECT COUNT(*) FROM food_log')).scalar()
print(f'Total logs: {result}')
"
```

## Success Criteria

✅ All UI components render without errors  
✅ Menu opens/closes smoothly  
✅ Sheets slide in/out properly  
✅ Copy creates new logs without affecting originals  
✅ Move removes from source and creates at target  
✅ Toast notifications appear and disappear  
✅ Daily logs refresh after operations  
✅ No console errors in browser  
✅ Mobile touch targets work well  
✅ Backend tests still pass (27/27)  

Enjoy the new copy/move functionality! 🎉
