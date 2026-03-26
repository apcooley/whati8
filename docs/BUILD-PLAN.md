# whati8 Build Plan

*Generated 2026-03-06 — Based on current codebase state and ROADMAP.md*

---

## Current State: Phase 3a (Profile Foods + Log + View)

**Branch:** `phase-3a-profile-foods` (uncommitted)
**Tests:** 159 collected
**Server:** Port 9428

### What's Built ✅

**Backend:**
- `user_foods` + `user_summary_nutrients` tables (2 Alembic migrations)
- `user_food_service.py` — 8 methods (CRUD, recent, frequent, search, favorites)
- `daily_log_service.py` — daily logs with nutrient rollups
- `formula_engine.py` — custom nutrient formulas (WW points etc.)
- `summary_config.py` router — per-user nutrient display config
- `profile.py` router — 6 endpoints for profile food CRUD
- `/logs/quick` endpoint for fast logging
- `/logs/daily/{date}` endpoint for daily view
- `unit` column on `food_logs` table

**Frontend (30 components):**
- `NavShell` — tabbed navigation (Log, Today, Add, Chat)
- `AddFoodView` — USDA search + manual entry + registration
- `RegisterSheet` — food registration with portion-based units
- `LogFoodView` — search profile foods, tap to log
- `QuickLogSheet` — quantity/unit/meal selection
- `ProfileFoodSearch` + `ProfileFoodItem` — profile browsing
- `DailyLogsView` — grouped by meal, day navigation
- `DayNavigator` — prev/next day arrows
- `MealGroup` + `LogEntry` — meal-grouped display
- `EditLogSheet` — inline editing of logged entries
- `DailySummaryBar` — customizable nutrient summary with config UI
- Meal assignment (4 standard meals) in QuickLogSheet

### What's Missing from 3a Spec ❌

| Feature | Effort | Priority |
|---------|--------|----------|
| Calendar date picker (currently prev/next only) | Small | Medium |
| "Copy yesterday's meal" shortcut | Medium | High — daily UX win |
| Completeness indicator (red/yellow/green) on profile foods | Small | Low — nice-to-have |
| Inline "add" fallback when profile search returns nothing | Small | Medium |

### Known Bugs / Polish

| Issue | Severity |
|-------|----------|
| Pydantic V2 deprecation warning (class-based config in `summary_config.py`) | Low |
| Everything uncommitted — needs commit + potential squash | Blocking |
| No frontend build pipeline / CI | Tech debt |

---

## Build Phases

### Phase 3a Wrap-Up (1-2 days)

**Goal:** Ship what's built, close remaining gaps, commit.

1. **Commit current work** — clean up, squash if needed, merge to main
2. **Copy yesterday's meal** — backend: `GET /logs/daily/{date}` already exists, add `POST /logs/copy-day`; frontend: button in LogFoodView
3. **Calendar picker** — add date input or simple calendar modal to DayNavigator
4. **Inline add fallback** — when profile search is empty, show "Search USDA" link that switches to Add tab with query pre-filled
5. **Fix Pydantic deprecation** — swap class-based config to `ConfigDict`
6. **End-to-end smoke test** — full flow: register → log → view → edit → delete

---

### Phase 3b: Dashboard & Reports (1-2 weeks)

**Goal:** Visualize nutrition data. Turn logs into insights.

**Backend:**
- `GET /dashboard/today` — macro breakdown, calorie/protein/points vs goals
- `GET /dashboard/week` — 7-day rolling averages
- `GET /dashboard/trends?range=30d` — time series data for charting
- Goal management CRUD (`user_goals` table already exists)
- Meal management CRUD (custom meals beyond the standard 4)
- Recipe management CRUD (composed of profile foods → `recipes` + `recipe_ingredients` tables exist)

**Frontend:**
- Dashboard tab (replace or augment Today view)
- Progress bars: calories, protein, points vs daily goals
- Weekly sparklines or bar charts (lightweight — Chart.js or uPlot)
- Goal settings screen (set targets for any nutrient)
- Recipe builder (select profile foods + quantities → save as recipe)

**Key Decision:** Whether Dashboard replaces the Today tab or becomes a new tab. Recommendation: merge into Today — show daily logs *above* the dashboard summary to keep it one screen.

---

### Phase 3c: Photo Recognition (3-5 days)

**Goal:** Snap a photo of food or a nutrition label → auto-identify and log.

**Backend:**
- `POST /foods/recognize` — accepts image, sends to Claude Vision API
- Returns structured food suggestions with confidence scores
- Nutrition label mode: OCR-extracts macros directly → creates custom food
- Rate limiting (Vision API is expensive)

**Frontend:**
- Camera capture button in Add and Log flows
- Preview + confirmation screen (edit suggestions before registering/logging)
- Nutrition label scanner mode (toggle)

**Dependencies:**
- Claude Vision API access (already using Claude for agent)
- Mobile camera permissions (PWA or native web)

---

### Phase 3d: Barcode Scanning (1-2 weeks)

**Goal:** Scan UPC → look up branded food → register to profile.

**Backend:**
- Barcode → UPC lookup service
- Data sources (pick one or both):
  - USDA Branded Foods (~400K items) — bulk import or on-demand query
  - OpenFoodFacts API — free, global, real-time lookup
- `POST /foods/barcode/{upc}` — returns food data or "not found"
- Auto-register scanned food to user profile

**Frontend:**
- Camera-based barcode scanner (`quagga2` or `zxing-js`)
- Scan button in Add flow
- Preview + register flow (same as USDA registration)

**Key Decision:** USDA Branded Foods is huge (~2GB import). Recommendation: start with OpenFoodFacts API for real-time lookup, add USDA Branded as batch import later if coverage gaps appear.

---

### Phase 3e: Voice Input (3-5 days)

**Goal:** Hands-free food logging via speech.

**Frontend:**
- Web Speech API integration (browser-native, no library needed)
- Microphone button on Log screen and Chat tab
- Visual feedback: recording indicator, transcription preview
- Auto-submit or confirm before sending to agent

**Backend:**
- No new endpoints needed — voice text routes through existing agent/chat flow
- Optional: dedicated `POST /agent/voice` for server-side transcription

---

### Phase 4: Production Hardening (2-3 weeks)

**Goal:** Make it reliable enough for daily use without babysitting.

| Item | Effort | Impact |
|------|--------|--------|
| Conversation persistence (in-memory → DB) | Medium | High |
| Streaming responses (SSE) | Medium | High |
| PWA support (installable, offline queue) | Medium | High |
| Push notifications (meal reminders, goals) | Small | Medium |
| Error recovery (AI retry, degradation) | Small | Medium |
| API versioning (`/v1/` prefix) | Small | Low |
| Frontend CI (build + lint on push) | Small | Medium |
| Config consolidation (`.env` + `config.toml`) | Small | Low |

---

## Recommended Build Order

```
NOW     Phase 3a wrap-up (commit + gaps)        1-2 days
NEXT    Phase 3b: Dashboard & Reports           1-2 weeks
THEN    Phase 4: Production Hardening           2-3 weeks  ← moved up
LATER   Phase 3c: Photo Recognition             3-5 days
LATER   Phase 3d: Barcode Scanning              1-2 weeks
LATER   Phase 3e: Voice Input                   3-5 days
```

**Why move Phase 4 before 3c-3e?**
- 3a + 3b give you a fully functional daily-driver app
- Production hardening (PWA, persistence, error recovery) makes it *reliable*
- Photo/barcode/voice are enhancements — nice but not blocking daily use
- You're already tracking daily; stability > features right now

---

## Tech Debt (Address Alongside)

- [ ] Integration tests against test DB (currently unit + edge only)
- [ ] Branded food data gap (no grocery products)
- [ ] Frontend test coverage (zero currently)
- [ ] Pydantic V2 migration (class-based config → ConfigDict)

---

*Solo dev with agent assistance. Timelines are working-session estimates, not calendar days.*
