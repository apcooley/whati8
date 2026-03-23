# Copy & Move Food Logs

## Overview

Users should be able to copy or move individual food logs (or entire meals) between dates. This speeds up daily logging when eating the same things repeatedly.

## API Endpoints

### `POST /logs/{log_id}/copy`

Duplicate a food log to a target date.

**Request:**
```json
{
  "target_date": "2026-03-22",
  "meal_id": 2
}
```
- `target_date` — required, the date to copy to
- `meal_id` — optional, defaults to the original log's meal_id

**Behavior:**
- Creates a new `food_log` with same `food_id`, `quantity`, `unit`, `user_food_id`, `notes`
- `logged_at` = `target_date` at noon (12:00:00) — naive datetime
- Returns the new log entry (FoodLogResponse)
- Auth: must own the source log

### `PATCH /logs/{log_id}/move`

Move a food log to a different date and/or meal.

**Request:**
```json
{
  "target_date": "2026-03-22",
  "meal_id": 2
}
```
- `target_date` — optional, new date (keeps original time-of-day)
- `meal_id` — optional, new meal assignment
- At least one must be provided

**Behavior:**
- Updates `logged_at` date portion while preserving time-of-day
- Updates `meal_id` if provided
- Returns the updated log entry
- Auth: must own the log

### `POST /logs/copy-meal`

Copy all logs from a specific meal on a source date to a target date.

**Request:**
```json
{
  "source_date": "2026-03-21",
  "source_meal_id": 2,
  "target_date": "2026-03-22",
  "target_meal_id": 2
}
```
- `source_date` — required
- `source_meal_id` — required (which meal to copy from)
- `target_date` — required (defaults to today in frontend)
- `target_meal_id` — optional, defaults to source_meal_id

**Behavior:**
- Finds all food_logs for user on source_date with source_meal_id
- Creates copies with target_date and target_meal_id
- `logged_at` = target_date at noon
- Returns list of new log entries
- Returns empty list if no source logs found (not an error)

## Frontend

- Long-press / swipe on log entry → **Copy** / **Move** actions
- Date picker defaults to today, meal picker defaults to current meal
- Copy-meal shortcut available per meal group

## Not Doing

- No "empty meal" prompts or suggestions
- No restrictions on future dates
