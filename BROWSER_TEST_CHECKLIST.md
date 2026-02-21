# Browser Testing Checklist - whati8 Multi-Food UI

**Date**: _______________  
**Tester**: _______________  
**Browser/Device**: _______________  
**Backend URL**: `http://192.168.1.11:15853`  
**Frontend URL**: `http://localhost:5173`

---

## Pre-Test Setup

- [ ] Backend running (`cd /home/aaron/source/whati8 && source .venv/bin/activate && uvicorn whati8.api.app:app --host 0.0.0.0 --port 15853`)
- [ ] Frontend running (`cd /home/aaron/source/whati8/frontend && npm run dev`)
- [ ] Test user logged in
- [ ] Browser DevTools open (Network + Console tabs)
- [ ] USDA data imported (8,058 foods, 14,574 portions)

---

## 1. Food Resolution (AI Parsing)

### 1.1 Single Food Items
| Test | Input | Expected | ✓/✗ |
|------|-------|----------|-----|
| Simple food | "an apple" | Parses: 1 apple | |
| With quantity | "2 eggs" | Parses: 2 eggs | |
| With unit | "1 cup rice" | Parses: 1 cup rice | |
| With size | "3 large eggs" | Parses: 3 large eggs | |
| With prep | "grilled chicken breast" | Parses: chicken breast (grilled) | |

### 1.2 Multiple Food Items
| Test | Input | Expected | ✓/✗ |
|------|-------|----------|-----|
| Two items | "2 eggs and toast" | 2 rows in form | |
| Three items | "eggs, bacon, and orange juice" | 3 rows in form | |
| Mixed units | "1 cup oatmeal and 2 bananas" | Correct units per row | |
| Comma separated | "chicken, rice, broccoli" | 3 rows | |

### 1.3 Meal Detection
| Test | Input | Expected | ✓/✗ |
|------|-------|----------|-----|
| Explicit breakfast | "eggs for breakfast" | Meal selector shows "Breakfast" | |
| Explicit lunch | "had a sandwich for lunch" | Meal selector shows "Lunch" | |
| Time-based (before 11am) | "2 eggs" | Auto-guesses "Breakfast" | |
| Time-based (11am-3pm) | "2 eggs" | Auto-guesses "Lunch" | |
| Time-based (3pm-8pm) | "2 eggs" | Auto-guesses "Dinner" | |
| Time-based (after 8pm) | "2 eggs" | Auto-guesses "Snack" | |

---

## 2. Household Portions (New Feature!)

### 2.1 Portion Matching
| Test | Input | Expected Calculation | ✓/✗ |
|------|-------|---------------------|-----|
| Eggs (large) | "3 large eggs" | 3 × 50g = 150g | |
| Eggs (medium) | "2 medium eggs" | 2 × 44g = 88g | |
| Cup of rice | "1 cup rice" | ~160-164g (varies by type) | |
| Tablespoon oil | "1 tbsp olive oil" | ~13.5g | |
| Chicken breast | "2 chicken breasts" | Matches "piece" portion if available | |

### 2.2 Portion Display
| Test | Expected | ✓/✗ |
|------|----------|-----|
| Matched portion shows gram calculation | "3 large → 150g" visible | |
| Unmatched unit falls back to serving | Shows default serving size | |
| Available portions shown in dropdown | Can see "1 cup", "1 tbsp", etc. | |

---

## 3. Multi-Food Confirmation Form

### 3.1 Form Display
| Test | Expected | ✓/✗ |
|------|----------|-----|
| Form appears after food resolution | Modal/form visible | |
| All parsed items shown as rows | Correct number of rows | |
| Each row shows food name | Names visible | |
| Each row shows quantity | Numbers visible | |
| Meal selector visible | Dropdown present | |
| Submit button visible | Button present | |
| Cancel/close option | X or Cancel button | |

### 3.2 Food Row Interactions
| Test | Action | Expected | ✓/✗ |
|------|--------|----------|-----|
| View food details | Look at row | Shows calories, protein, fat | |
| Change quantity | Edit quantity field | Updates total nutrients | |
| Delete row | Click delete/X | Row removed from form | |
| Delete last row | Delete all rows | Submit button disabled/grayed | |

### 3.3 Food Selector (Dropdown)
| Test | Action | Expected | ✓/✗ |
|------|--------|----------|-----|
| Open dropdown | Click food name | Shows alternatives | |
| See alternatives | Look at dropdown | Other matched foods visible | |
| Select alternative | Click different food | Row updates with new food | |
| Search for food | Type in search box | Results appear | |
| Search shows spinner | While searching | Loading indicator visible | |
| Select from search | Click search result | Row updates | |
| Click outside | Click away from dropdown | Dropdown closes, reverts to previous | |
| Cancel edit | Click Cancel button | Returns to previous selection | |

### 3.4 Inline Add Food
| Test | Action | Expected | ✓/✗ |
|------|--------|----------|-----|
| Find "Add food" button | Look at form | Button/link visible | |
| Click add food | Click button | Search input appears | |
| Search new food | Type food name | Results appear | |
| Add food to form | Select from results | New row added | |
| Cancel add | Click cancel | Input disappears | |

### 3.5 Meal Selector
| Test | Action | Expected | ✓/✗ |
|------|--------|----------|-----|
| See current meal | Look at selector | Shows guessed/selected meal | |
| Change meal | Click and select different | Updates to new meal | |
| Options available | Open dropdown | Breakfast, Lunch, Dinner, Snack | |

---

## 4. Form Submission

### 4.1 Successful Submit
| Test | Action | Expected | ✓/✗ |
|------|--------|----------|-----|
| Submit with foods | Click Submit | Loading state shown | |
| Success response | Wait for completion | Success message/confirmation | |
| Form closes | After success | Modal/form disappears | |
| Data persisted | Check DB or food log | Entries created | |

### 4.2 Error Handling
| Test | Action | Expected | ✓/✗ |
|------|--------|----------|-----|
| Network error | Disable network, submit | Error message shown | |
| Validation error | Submit invalid data | Clear error message | |
| Partial failure | (if applicable) | Rollback message | |

### 4.3 Empty State
| Test | Action | Expected | ✓/✗ |
|------|--------|----------|-----|
| All rows deleted | Delete all food rows | Submit button disabled | |
| Submit disabled appearance | Look at button | Grayed out / not clickable | |

---

## 5. Mobile/Touch Testing

### 5.1 Touch Targets (min 44px)
| Element | Meets 44px? | ✓/✗ |
|---------|-------------|-----|
| Delete row button | | |
| Food selector dropdown | | |
| Quantity input | | |
| Meal selector | | |
| Submit button | | |
| Cancel button | | |
| Search input | | |

### 5.2 Responsive Layout
| Test | Screen Width | Expected | ✓/✗ |
|------|--------------|----------|-----|
| Mobile portrait | 375px | All elements visible, usable | |
| Mobile landscape | 667px | Layout adapts | |
| Tablet | 768px | Good spacing | |
| Desktop | 1200px+ | Full layout | |

### 5.3 Touch Interactions
| Test | Action | Expected | ✓/✗ |
|------|--------|----------|-----|
| Tap food selector | Tap | Dropdown opens | |
| Scroll dropdown | Swipe | Scrolls smoothly | |
| Tap outside dropdown | Tap elsewhere | Closes dropdown | |
| Long press (if applicable) | Long press | No unexpected behavior | |

---

## 6. Loading States & Feedback

### 6.1 Spinners/Loading
| Test | When | Expected | ✓/✗ |
|------|------|----------|-----|
| Initial food resolution | Parsing input | Loading indicator | |
| Food search | Typing in search | Row-level spinner | |
| Form submit | Clicking submit | Form-level loading | |

### 6.2 Disabled States
| Test | When | Expected | ✓/✗ |
|------|------|----------|-----|
| During submit | Form submitting | All inputs disabled | |
| Empty form | No food rows | Submit disabled | |

---

## 7. Edge Cases

### 7.1 Special Inputs
| Test | Input | Expected | ✓/✗ |
|------|-------|----------|-----|
| Unicode food | "2 açaí bowls" | Parses correctly | |
| Numeric words | "two eggs" | Converts to 2 | |
| Fractions | "1/2 cup milk" | Parses as 0.5 | |
| Decimal | "1.5 cups flour" | Parses as 1.5 | |
| Very long input | 500+ char description | Handles gracefully | |

### 7.2 No Match Scenarios
| Test | Input | Expected | ✓/✗ |
|------|-------|----------|-----|
| Unknown food | "xyzfood123" | Shows "not found" status | |
| Ambiguous food | "salad" | Shows multiple options | |
| Misspelled food | "chiken" | Fuzzy match finds chicken | |

### 7.3 Deduplication
| Test | Input | Expected | ✓/✗ |
|------|-------|----------|-----|
| Same food, different portions | DB has 100g and cup | Prefers human-readable (cup) | |

---

## 8. API Verification (DevTools Network Tab)

### 8.1 Endpoints Called
| Endpoint | Method | When | ✓/✗ |
|----------|--------|------|-----|
| `/agent/chat` | POST | Food resolution | |
| `/foods/search` | GET | Food search | |
| `/logs/batch` | POST | Form submit | |

### 8.2 Request/Response
| Check | Expected | ✓/✗ |
|-------|----------|-----|
| Auth header present | `Authorization: Bearer ...` | |
| Content-Type correct | `application/json` | |
| No 4xx errors | All 200/201 | |
| No 5xx errors | No server errors | |
| Response times reasonable | < 2s for most operations | |

---

## 9. Console Errors

| Check | Expected | ✓/✗ |
|-------|----------|-----|
| No JavaScript errors | Console clean | |
| No network errors (red) | No failed requests | |
| No Svelte warnings | No component warnings | |

---

## 10. Accessibility (Optional)

| Check | Expected | ✓/✗ |
|-------|----------|-----|
| Keyboard navigation | Tab through form works | |
| Focus visible | Can see focused element | |
| Screen reader labels | Inputs have labels | |
| Color contrast | Text readable | |

---

## Test Results Summary

| Category | Passed | Failed | Notes |
|----------|--------|--------|-------|
| Food Resolution | /5 | | |
| Multiple Items | /4 | | |
| Meal Detection | /6 | | |
| Household Portions | /5 | | |
| Form Display | /6 | | |
| Row Interactions | /4 | | |
| Food Selector | /8 | | |
| Inline Add | /4 | | |
| Meal Selector | /3 | | |
| Submission | /7 | | |
| Mobile/Touch | /11 | | |
| Loading States | /5 | | |
| Edge Cases | /9 | | |
| API | /6 | | |
| **TOTAL** | **/83** | | |

---

## Issues Found

| # | Severity | Description | Steps to Reproduce |
|---|----------|-------------|-------------------|
| 1 | | | |
| 2 | | | |
| 3 | | | |

---

## Notes

```
(Add any observations, suggestions, or context here)
```
