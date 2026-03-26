# Phase 3a: Profile Foods + Log + View Logs — Technical Design

## Overview

Replace the chat-first UI with an action-based interface. Three core flows:

1. **Add a Food** — Register foods to a personal profile (from USDA, manual entry, or later photo/barcode)
2. **Log a Food** — Search profile foods and log with quantity/meal
3. **View Logs** — Daily view grouped by meal, with inline editing and nutrient summary

---

## Data Model Changes

### New Table: `user_foods` (Profile Library)

The key new concept: a **user_foods** junction table that links users to foods they've registered. This is distinct from `food_logs` (what you ate) and `foods` (the master catalog).

```sql
CREATE TABLE user_foods (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    food_id         INTEGER NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
    nickname        VARCHAR(100),       -- user's custom name ("My protein shake")
    default_quantity NUMERIC(10,2),     -- preferred serving (e.g., 2.0)
    default_unit    VARCHAR(50),        -- preferred unit (e.g., "scoop")
    default_meal_id INTEGER REFERENCES meals(id) ON DELETE SET NULL,
    is_favorite     BOOLEAN DEFAULT FALSE,
    use_count       INTEGER DEFAULT 0,  -- incremented on each log
    last_used_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, food_id)
);

CREATE INDEX ix_user_foods_user_id ON user_foods(user_id);
CREATE INDEX ix_user_foods_user_favorite ON user_foods(user_id, is_favorite);
CREATE INDEX ix_user_foods_user_use_count ON user_foods(user_id, use_count DESC);
```

**Why a junction table instead of a flag on `foods`?**
- USDA foods are shared across all users — can't add per-user metadata to `foods`
- Each user gets their own nickname, default quantity, favorite status
- `use_count` + `last_used_at` power the "Recent" and "Frequent" sections
- Clean separation: `foods` = catalog, `user_foods` = personal library, `food_logs` = consumption history

### New Table: `user_summary_nutrients`

Controls which nutrients appear in the daily summary bar per user.

```sql
CREATE TABLE user_summary_nutrients (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    nutrient_id     INTEGER NOT NULL REFERENCES nutrients(id) ON DELETE CASCADE,
    display_order   INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, nutrient_id)
);
```

Default for new users: Calories, Protein, Carbs, Fat, Fiber (seeded on registration).

### Changes to Existing Tables

**`food_logs`** — add `user_food_id` (nullable FK to `user_foods`):
- Links log entry back to the profile food for defaults/stats
- Nullable because legacy logs and agent-created logs may not go through profile
- On log creation via profile flow, auto-increment `user_foods.use_count` and update `last_used_at`

**No changes to:** `foods`, `food_nutrients`, `food_portions`, `nutrients`, `meals`, `user_goals`, `recipes`, `recipe_ingredients`

---

## SQLAlchemy Models

### `whati8/models/user_food.py` (new)

```python
class UserFood(Base, TimestampMixin):
    __tablename__ = "user_foods"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id", ondelete="CASCADE"))
    nickname: Mapped[str | None] = mapped_column(String(100), nullable=True)
    default_quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    default_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    default_meal_id: Mapped[int | None] = mapped_column(
        ForeignKey("meals.id", ondelete="SET NULL"), nullable=True
    )
    is_favorite: Mapped[bool] = mapped_column(default=False)
    use_count: Mapped[int] = mapped_column(default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="user_foods")
    food: Mapped["Food"] = relationship()
    default_meal: Mapped["Meal | None"] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "food_id", name="uq_user_food"),
        Index("ix_user_foods_user_id", "user_id"),
        Index("ix_user_foods_user_favorite", "user_id", "is_favorite"),
    )
```

### `whati8/models/user_summary_nutrient.py` (new)

```python
class UserSummaryNutrient(Base, TimestampMixin):
    __tablename__ = "user_summary_nutrients"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    nutrient_id: Mapped[int] = mapped_column(ForeignKey("nutrients.id", ondelete="CASCADE"))
    display_order: Mapped[int] = mapped_column(default=0)

    user: Mapped["User"] = relationship()
    nutrient: Mapped["Nutrient"] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "nutrient_id", name="uq_user_summary_nutrient"),
    )
```

---

## API Endpoints

### Profile Foods (`/profile/foods`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/profile/foods` | List user's profile foods (search, sort, pagination) |
| `GET` | `/profile/foods/recent` | Top 10 most recently used |
| `GET` | `/profile/foods/frequent` | Top 10 most frequently used |
| `POST` | `/profile/foods/register` | Register food to profile (by food_id or manual entry) |
| `PUT` | `/profile/foods/{id}` | Update nickname, defaults, favorite status |
| `DELETE` | `/profile/foods/{id}` | Remove from profile (doesn't delete the food) |

**`GET /profile/foods`** query params:
- `q` (string) — filter by name/nickname (ILIKE)
- `sort` (enum: `recent`, `frequent`, `alpha`, `favorite`) — default `recent`
- `limit`, `offset` — pagination

**`POST /profile/foods/register`** body options:
```json
// Option A: Register existing food from USDA/app DB
{
  "food_id": 1234,
  "nickname": "My eggs",
  "default_quantity": 2.0,
  "default_unit": "piece",
  "default_meal_id": 1,
  "is_favorite": true
}

// Option B: Create custom food AND register in one step
{
  "custom_food": {
    "name": "Homemade Granola",
    "serving_size": 50,
    "unit": "g",
    "calories": 220,
    "protein": 5,
    "carbs": 30,
    "fat": 10,
    "fiber": 3
  },
  "nickname": "Granola",
  "default_quantity": 1.0,
  "default_unit": "serving",
  "is_favorite": false
}
```

### Food Logging (enhanced)

Existing endpoints unchanged. New additions:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/logs/quick` | Log from profile food (uses defaults, increments use_count) |
| `GET` | `/logs/daily/{date}` | Logs for a date, grouped by meal, with nutrient summary |

**`POST /logs/quick`** body:
```json
{
  "user_food_id": 42,
  "quantity": 2.0,        // optional — falls back to user_food.default_quantity
  "unit": "piece",        // optional — falls back to user_food.default_unit
  "meal_id": 1,           // optional — falls back to user_food.default_meal_id
  "logged_at": "..."      // optional — defaults to now
}
```

**`GET /logs/daily/2026-03-02`** response:
```json
{
  "date": "2026-03-02",
  "meals": [
    {
      "meal": {"id": 1, "name": "Breakfast"},
      "logs": [
        {
          "id": 501,
          "food": {"id": 102, "name": "Egg, whole, raw"},
          "quantity": 2.0,
          "unit": "piece",
          "logged_at": "2026-03-02T08:30:00-07:00",
          "calories": 144,
          "protein": 12.6
        }
      ]
    }
  ],
  "summary": {
    "nutrients": [
      {"name": "Calories", "value": 1850, "target": 2000, "unit": "kcal"},
      {"name": "Protein", "value": 142, "target": 200, "unit": "g"}
    ]
  }
}
```

### Summary Nutrients (`/profile/summary-nutrients`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/profile/summary-nutrients` | Get user's chosen summary nutrients |
| `PUT` | `/profile/summary-nutrients` | Replace list (array of nutrient_ids with order) |

---

## Frontend Architecture

### Navigation Shell

Replace `App.svelte` → `ChatContainer` with a tabbed shell:

```
App.svelte
└── NavShell.svelte              (bottom tab bar + content area)
    ├── LogFoodView.svelte       (📝 Log — default tab)
    ├── DailyLogsView.svelte     (📋 Today)
    ├── AddFoodView.svelte       (➕ Add)
    └── ChatView.svelte          (🤖 Chat — existing ChatContainer)
```

### Tab 1: 📝 Log a Food (`LogFoodView.svelte`)

```
┌─────────────────────────────┐
│  🔍 Search your foods...     │  ← search-as-you-type
├─────────────────────────────┤
│  ⭐ FAVORITES                │
│  🥚 Eggs (2 piece)      [+] │  ← [+] logs with defaults
│  🥜 PB Bar (1 bar)      [+] │
├─────────────────────────────┤
│  🕐 RECENT                   │
│  🍳 Oatmeal (1 cup)     [+] │
│  🥗 Chicken breast      [+] │
├─────────────────────────────┤
│  📋 Copy yesterday's...      │
├─────────────────────────────┤
│  Can't find it?              │
│  [Search USDA →]             │  ← opens Add flow, register+log
└─────────────────────────────┘
```

**Components:**
- `ProfileFoodSearch.svelte` — search input + filtered results
- `ProfileFoodItem.svelte` — food row with [+] quick-log + expand for custom qty
- `QuickLogSheet.svelte` — bottom sheet for editing qty/unit/meal before logging
- `CopyMealButton.svelte` — copies logs from a previous meal

### Tab 2: 📋 Today (`DailyLogsView.svelte`)

```
┌─────────────────────────────┐
│  ◀  Mon, Mar 2, 2026   ▶  📅│
├─────────────────────────────┤
│  🌅 BREAKFAST                │
│  Eggs × 2 piece        144c │  ← tap to edit, swipe to delete
│  Oatmeal × 1 cup       150c │
├─────────────────────────────┤
│  🌙 DINNER                   │
│  (no foods logged)     [+]  │
├─────────────────────────────┤
│  Calories: 780 / 2000  ████░│
│  Protein:  62 / 200g   ██░░░│
└─────────────────────────────┘
```

**Components:**
- `DayNavigator.svelte` — date arrows + calendar picker
- `MealGroup.svelte` — meal header + log entries
- `LogEntry.svelte` — single log, tap → edit, swipe → delete
- `DailySummaryBar.svelte` — nutrient progress bars

### Tab 3: ➕ Add a Food (`AddFoodView.svelte`)

```
┌─────────────────────────────┐
│  Add to Your Foods           │
├─────────────────────────────┤
│  🔍 Search USDA database... │  ← existing hybrid search
│  Results:                    │
│  Egg, whole, raw (50g)  [+] │  ← registers to profile
├─────────────────────────────┤
│  — or —                      │
│  [✏️ Enter Manually]         │
│  [📷 Take Photo] (coming)   │
│  [📱 Scan Barcode] (coming) │
└─────────────────────────────┘
```

**Components:**
- `USDASearch.svelte` — reuses existing search endpoint
- `ManualFoodForm.svelte` — refactored from existing `AddFoodModal`
- `RegisterSheet.svelte` — set nickname, defaults, favorite

### Tab 4: 🤖 Chat (`ChatView.svelte`)

Existing `ChatContainer.svelte`. No changes initially.

---

## Implementation Plan

| Step | Scope | Files |
|------|-------|-------|
| 1 | DB migration | `alembic/versions/xxx_add_user_foods.py` |
| 2 | Models + schemas | `models/user_food.py`, `models/user_summary_nutrient.py`, `schemas/user_food.py`, `schemas/daily_log.py` |
| 3 | Service layer | `services/user_food_service.py`, `services/daily_log_service.py` |
| 4 | API routes | `api/routers/profile.py`, updates to `food_log.py`, register in `app.py` |
| 5 | Frontend nav shell | `NavShell.svelte`, update `App.svelte` |
| 6 | Frontend — Log tab | `LogFoodView.svelte`, `ProfileFoodSearch.svelte`, `ProfileFoodItem.svelte`, `QuickLogSheet.svelte`, stores + API |
| 7 | Frontend — Daily view | `DailyLogsView.svelte`, `DayNavigator.svelte`, `MealGroup.svelte`, `LogEntry.svelte`, `DailySummaryBar.svelte` |
| 8 | Frontend — Add tab | `AddFoodView.svelte`, `USDASearch.svelte`, `ManualFoodForm.svelte`, `RegisterSheet.svelte` |
| 9 | Integration | Cross-tab flows, "Copy meal", toasts, error handling, mobile gestures |

---

## Migration Strategy

- Chat UI keeps working throughout — new UI is additive
- Old endpoints unchanged; new endpoints are parallel (`/profile/*`, `/logs/quick`, `/logs/daily/*`)
- `food_logs.user_food_id` is nullable — legacy logs unaffected
- Feature flag or nav toggle during dev; Log tab becomes default when stable

---

## Open Questions

1. **Profile food limit?** Uncapped for now. Server-side search if someone exceeds ~500.
2. **Auto-register on agent log?** When agent logs via chat, auto-add to profile? Leaning yes.
3. **Recipes in Log tab?** Probably yes, but follow-up in 3b after recipe CRUD exists.
