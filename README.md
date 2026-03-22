# whati8

**AI-powered food and nutrition tracker**

## Technology Stack

| Component          | Technology                 | Notes                                         |
|:-------------------|:---------------------------|:----------------------------------------------|
| **Backend**        | Python, FastAPI            | High-performance API layer.                   |
| **Database**       | SQLAlchemy (ORM)           | For robust, idiomatic database interaction.   |
| **Data Source**    | USDA Food Data Central     | Core nutrition data provider.                 |
| **AI/LLM**         | Anthropic Claude (default) | Natural language food parsing and resolution. |
| **Search**         | pg_trgm + pgvector + Cohere | Hybrid trigram/semantic search with reranking. |
| **Embeddings**     | Cohere embed-v3 / Ollama   | 768d semantic vectors (dual-provider fallback).|
| **Authentication** | FastAPI OAuth2 + JWT       | Secure user session management.               |

---

## Key Features

*   **Easy To Use:** Unlike other products which require a lot of typing, searching, and fiddling, you just type in natural text, dictate with voice, or even snap a pic of your food and it does the rest.
*   **Highly Customizable**: Add your own foods, recipes, meals, and nutrition tracking methodology (caliories, protein, weight watchers, etc.). whati8 molds to your approach.
*   **Database Search:** Utilizing optimized database queries and fuzzy matching for rapid food lookup. Starts with over 50,000 foods already loaded.
*   **Hybrid Search:** Three-layer search pipeline — trigram fuzzy match, semantic embeddings (Cohere/Ollama), and Cohere Rerank 3 — with configurable strategies via `config.toml`.
*   **Personalized Goals:** Adherence to user-defined macro targets (Protein, Carbs, Fat) and daily calorie budgets (Default: ~1850 kcal).
*   **Secure & Scalable:** Built on a modern Python stack for maintainability and growth.

---

## Production Readiness ✅

**Status:** Production-ready with smart food logging and nutrition summaries (as of Feb 10, 2026)

### Fully Functional Features
- ✅ **Conversational Agent:** Multi-turn tool calling, natural language food logging, auto-triggered food selection modals
- ✅ **7 Agent Tools:** log_food, search_foods, resolve_foods_nl, list_logs, get_daily_summary, delete_log, show_confirmation_form
- ✅ **Smart Unit Handling:** Editable quantities + unit dropdowns with valid conversions per food (Feb 10)
- ✅ **Batch-Summary Endpoint:** Logs foods, calculates nutrition totals, Claude formats friendly summary (Feb 10)
- ✅ **Server Auto-Kill:** `uv run python -m whati8 serve` auto-kills existing process on port conflict (Feb 10)
- ✅ **Smart Deduplication:** Automatically prefers human-readable portions (e.g., "69g/fruit") over generic 100g servings
- ✅ **Local Timestamps:** All chat timestamps display in user's local timezone
- ✅ **Frontend UI:** Svelte 4 + Tailwind CSS, mobile-first responsive design, JWT authentication
- ✅ **Performance:** Non-blocking async throughout, N+1 query optimization (21→2 queries)
- ✅ **Security:** CORS restrictions, rate limiting (10/min general, 5/min AI), input sanitization, security headers, bcrypt 4.0.1
- ✅ **Reliability:** Startup health checks, comprehensive logging, graceful error handling
- ✅ **Code Quality:** All magic numbers extracted to constants, standardized error responses, base schema classes
- ✅ **Validation:** Strong JWT secret validation, API key format checks, enhanced Pydantic validation
- ✅ **Testing:** 27/27 food unit tests + 41 comprehensive edge cases passing

### Search Quality (Feb–Mar 2026)
- ✅ **Hybrid Search:** Trigram + semantic embedding search with configurable weights (`config.toml`)
- ✅ **Cohere Embeddings:** embed-english-v3 (768d) with Ollama nomic-embed-text fallback
- ✅ **pgvector Integration:** Dual embedding columns (one per provider, not interchangeable)
- ✅ **Cohere Rerank 3:** Configurable strategies (word_count, confidence, always, never)
- ✅ **Search Analytics:** Logs user selections with per-method ranking for quality tuning
- ✅ **TOML Config:** `config.toml` for search weights, rerank strategy, and thresholds

### Recent Updates (Feb 10, 2026)

#### Food Confirmation Form UI
1. **Editable Quantity Input** - Changed from button to number input
2. **Unit Dropdown** - Shows only valid conversions for each food
3. **Cleaner Display** - Format: `[qty input] [unit dropdown]` with modifiers shown
4. **No Grams Unless Selected** - Grams column only shows if user selected "g" unit

#### Smart Food Logging Flow
1. User types: "1 egg, 2 peanut butter bars"
2. Agent responds: "Searching database..."
3. Form pops up with foods and editable quantities/units
4. User reviews and clicks "Log Foods"
5. **NEW:** System logs foods + queries them back + calculates nutrition totals
6. **NEW:** Claude formats summary: "You logged 1 egg (1 cup) and 2 bars. Total: 2500 kcal, 48g protein, 39g carbs, 40g fat, 0g fiber."
7. Summary displays in chat

#### Improvements
1. **Batch-Summary Endpoint** - `/logs/batch-summary` combines logging + Claude formatting in one call
2. **No Empty Agent Messages** - "Searching database..." shown instead of silent form
3. **Better Form Feedback** - Summary message confirms what was actually logged
4. **Auto-Server-Kill** - Port conflicts resolved automatically with `--kill-existing` (default)
5. **Bcrypt Fix** - Downgraded to 4.0.1 for passlib compatibility

### Data Quality (Mar 22, 2026)
- ✅ **Energy stored as kcal:** All nutrients stored in kcal (was kJ), no more conversion math
- ✅ **Energy coalesce:** `COALESCE(Atwater General, Atwater Specific, Plain Energy)` — Foundation foods use nutrition-label-standard values
- ✅ **Carb coalesce:** `COALESCE(by summation, MAX(by difference, 0))` — negative carbs clamped, summation preferred
- ✅ **USDA dedup:** Foundation preferred over SR Legacy; dedup runs automatically during import
- ✅ **Naive timestamps:** `logged_at` stores wall-clock time (no timezone), not UTC
- ✅ **Multi-unit servings:** `serving_quantity` correctly splits portion weight (e.g., "4 slices = 56g" → 14g/slice)

### Test Results
- ✅ 38 tests passing across 4 test suites (kcal migration, nutrient coalesce, naive datetime, serving quantity)
- ✅ Plus existing tests (volume portions, recipe search, recipe portions)
- ✅ All tests run against live PostgreSQL database

---

## How It Works: Smart Food Logging (Feb 10, 2026)

### The Flow

1. **User Types:** "I had 1 egg and 2 peanut butter bars"

2. **Agent Responds:** "Searching database..."
   - The agent calls `resolve_foods_nl` to parse your input
   - Claude generates search terms and queries the database
   - System finds matching foods (Egg, whole, raw vs. Peanut Butter Cup)

3. **Confirmation Form Appears** with editable details:
   ```
   □ Egg, whole, raw, fresh | [1.0] [piece ▼]
   □ Peanut Butter Cup bar   | [2.0] [piece ▼]
   
   Meal: [Breakfast ▼]
   [+ Add another food]  [Cancel]  [✓ Log Foods]
   ```
   - You can edit quantities (numbers change)
   - You can change units (dropdown shows valid conversions)
   - Units respect food types (pieces, cups, grams, etc.)

4. **You Click "Log Foods"** and the magic happens:
   - Foods are logged to your database
   - Nutrition data is queried back (calories, protein, carbs, fat, fiber)
   - **Claude automatically formats a summary** (Feb 10 NEW):

   ```
   You logged 1 egg (1 piece) and 2 peanut butter bars.
   Total: 350 calories, 18g protein, 5g carbs, 28g fat, 0g fiber.
   ```

5. **Summary Appears in Chat** and you're done!

### Key Improvements (Feb 10)

- **Editable Quantities:** No longer clicking buttons—type the amount directly
- **Smart Unit Dropdowns:** Only shows units that make sense for each food
  - Egg: piece, cup, oz, g
  - Peanut Butter: bar, tbsp, oz, g
- **Smart Form Message:** "Searching database..." instead of silence
- **Auto Summary:** Claude formats a friendly confirmation message
- **Auto Server Kill:** Running the server twice doesn't crash—old process auto-killed

---

## Setup & Installation

### Prerequisites
*   **Python 3.10+** (3.11 or 3.12 recommended)
*   **PostgreSQL 14+** - Database engine
*   **git** - For cloning/syncing
*   **API Keys** (obtain before starting):
    *   [USDA Food Data Central](https://fdc.nal.usda.gov/api-key-signup.html) - Free, instant approval
    *   [Anthropic API](https://console.anthropic.com/) - For Claude (recommended), or
    *   [OpenAI API](https://platform.openai.com/) - For GPT-4

### 1. Clone Repository
```bash
git clone https://github.com/aaronpcooley/whati8.git whati8
cd whati8
```

### 2. Environment Setup
Create and activate a Python virtual environment:
```bash
uv venv
```

### 3. Install Dependencies
```bash
uv sync
```

### 4. Environment Configuration
Create a `.env` file in the project root:

```bash
# Database
DATABASE_URL=postgresql://whati8:whati8@localhost:5432/whati8

# USDA Food Data Central API
# Get your key at: https://fdc.nal.usda.gov/api-key-signup.html
USDA_API_KEY=YOUR_USDA_API_KEY_HERE

# AI/LLM Service (choose one)
# Anthropic Claude (recommended for function calling)
ANTHROPIC_API_KEY=YOUR_ANTHROPIC_KEY_HERE
# Or OpenAI
# OPENAI_API_KEY=YOUR_OPENAI_KEY_HERE

# Authentication
# IMPORTANT: Use a strong random string (min 32 chars, 10+ unique)
# Generate with: openssl rand -hex 32
JWT_SECRET=your-secret-key-change-in-production-use-openssl-rand-hex-32
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Application
DEBUG=true
LOG_LEVEL=info

# CORS Configuration (Required for production)
# Comma-separated list of allowed origins
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=10
RATE_LIMIT_AI_PER_MINUTE=5
```

**Important Notes:**
- Never commit `.env` to version control. A `.env.example` template is provided.
- JWT_SECRET must be at least 32 characters with 10+ unique characters for production.
- ANTHROPIC_API_KEY must start with `sk-ant-` (validated on startup).
- Update ALLOWED_ORIGINS for your production frontend domains.

### 5. Database Setup

**Option A: Automated Setup (Recommended)**
```bash
./scripts/setup_db.sh
```

This script will:
- Create PostgreSQL database and user
- Enable pg_trgm extension for fuzzy search
- Run Alembic migrations to create all tables

**Option B: Manual Setup**
```bash
# Create database and user
sudo -u postgres psql -c "CREATE USER whati8 WITH PASSWORD 'whati8';"
sudo -u postgres psql -c "CREATE DATABASE whati8 OWNER whati8;"
sudo -u postgres psql -d whati8 -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"

# Run migrations
uv run alembic upgrade head
```

**Verify Setup:**
```bash
# Run verification script
uv run scripts/verify_setup.py

# Check tables were created
psql -U whati8 -d whati8 -c "\dt"
```

**Import USDA Food Data:**
```bash
# Management script for bulk import (coming soon)
uv run python -m whati8.cli import-usda-data
```

*Note: Initial USDA data import downloads ~500MB and takes 5-10 minutes. You'll need your USDA API key configured in `.env`.*

---

## Using the API

### Start the Server

```bash
# Development server with auto-reload (accessible over LAN)
uv run python -m whati8 serve --reload
```

The server will start on `http://0.0.0.0:8000` by default, making it accessible:
- **Locally**: http://localhost:8000
- **From LAN**: http://192.168.1.11:8000 (replace with your server IP)

### API Documentation

**Interactive Documentation** (try endpoints in your browser):
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Authentication Flow

1. **Register a new user:**
   ```bash
   curl -X POST http://localhost:8000/auth/register \
     -H "Content-Type: application/json" \
     -d '{"username":"testuser","email":"test@example.com","password":"password123"}'
   ```

2. **Login to get JWT token:**
   ```bash
   TOKEN=$(curl -X POST http://localhost:8000/auth/login \
     -H "Content-Type: application/json" \
     -d '{"login":"testuser","password":"password123"}' \
     | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
   ```

3. **Access protected endpoints:**
   ```bash
   curl http://localhost:8000/auth/me \
     -H "Authorization: Bearer $TOKEN"
   ```

### CLI Alternative

For terminal usage, CLI commands are also available:
```bash
# Register
uv run python -m whati8 auth register

# Login
uv run python -m whati8 auth login

# Validate token
uv run python -m whati8 auth whoami <token>
```

### Testing

Run the automated test suite:
```bash
./scripts/test_api.sh
```

---

## Architecture Decisions

### AI/LLM Service: Anthropic Claude (Default)
- **Why:** Excellent function calling for structured output, 200K context for food databases
- **Alternative:** OpenAI GPT-4 (swap `ANTHROPIC_API_KEY` for `OPENAI_API_KEY`)
- **Cost:** ~$0.01-0.05 per food logging interaction

### Database: PostgreSQL
- **Why:** Full-text search (tsvector), JSON support, mature ecosystem
- **Search Strategy:** pg_trgm trigram indexes for fuzzy food name matching
- **Migrations:** Alembic for schema versioning

### USDA Data Source
- **Using:** FoodData Central API + Bulk JSON download
- **Databases Included:**
  - Foundation Foods (core nutrients, ~1,000 foods)
  - SR Legacy (legacy USDA database, ~8,000 foods)
  - Branded Foods (grocery products, ~400,000 foods - selective import)
- **Update Frequency:** Quarterly bulk refresh

### User Authentication
- **Strategy:** JWT tokens with FastAPI OAuth2 password flow
- **Security:** Passwords hashed with bcrypt, tokens expire in 24h
- **Multi-tenancy:** All data scoped by `user_id` foreign keys

---

## Documentation

- **[CURRENT_STATUS.md](CURRENT_STATUS.md)** - Quick reference with current state, known issues, debugging tips (start here)
- **[IMPLEMENTATION.md](IMPLEMENTATION.md)** - Complete implementation guide: schema design, auth system, API reference, setup instructions
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design, data flow, and design decisions
- **[ROADMAP.md](ROADMAP.md)** - Development roadmap with phase breakdown
- **[CLAUDE.md](CLAUDE.md)** - Instructions for Claude Code AI assistant
- **[.env.example](.env.example)** - Environment configuration template
- **API Docs** - Interactive documentation at http://localhost:8000/docs (when server running)

---

## Quick Reference

### Scripts
```bash
# Setup database (automated)
./scripts/setup_db.sh

# Verify setup
uv run scripts/verify_setup.py

# Run migrations
uv run alembic upgrade head

# Check migration status
uv run alembic current

# Rollback migration
uv run alembic downgrade -1
```

### Database Commands
```bash
# Connect to database
psql -U whati8 -d whati8

# List tables
psql -U whati8 -d whati8 -c "\dt"

# Describe table
psql -U whati8 -d whati8 -c "\d users"

# List indexes
psql -U whati8 -d whati8 -c "\di"
```

### Development
```bash
# Install dependencies
uv sync

# Run tests (when available)
uv run pytest

# Start API server (development with auto-reload)
uv run python -m whati8 serve --reload

# Access API documentation
# - Swagger UI: http://localhost:8000/docs
# - ReDoc: http://localhost:8000/redoc

# Test API endpoints
./scripts/test_api.sh
```

---

## Domain Model

### Database Schema Overview

The whati8 application uses a **flexible, normalized relational database** with **9 tables** to support customizable nutrition tracking. The key innovation is that nutrients, goals, and meals are stored as data (not hardcoded columns), allowing users to track whatever matters to them.

#### Entity-Relationship Diagram

```
                    ┌─────────────┐
                    │    User     │
                    │─────────────│
                    │ id (PK)     │
                    │ username    │
                    │ email       │
                    │ password    │
                    └─────────────┘
                           │
         ┌─────────────────┼─────────────────┬─────────────────┐
         │                 │                 │                 │
         ▼                 ▼                 ▼                 ▼
  ┌───────────┐     ┌───────────┐    ┌──────────┐     ┌──────────┐
  │ UserGoal  │     │   Food    │    │  Recipe  │     │   Meal   │
  │───────────│     │───────────│    │──────────│     │──────────│
  │ user_id   │     │ name      │    │ user_id  │     │ name     │
  │ goal_type │     │ brand     │    │ name     │     │ user_id  │
  │ target    │     │ serving_* │    │ desc     │     │ order    │
  └───────────┘     │ usda_id   │    └──────────┘     └──────────┘
   (key-value)      │ user_id   │          │                │
                    └───────────┘          │                │
                          │                │                │
              ┌───────────┼────────┐       │                │
              │           │        │       │                │
              ▼           ▼        ▼       ▼                ▼
       ┌───────────┐ ┌──────────────┐ ┌───────────┐ ┌──────────┐
       │ Nutrient  │ │ FoodNutrient │ │  Recipe   │ │ FoodLog  │
       │───────────│ │──────────────│ │ Ingredient│ │──────────│
       │ name      │ │ food_id      │ │───────────│ │ user_id  │
       │ unit      │ │ nutrient_id  │ │ recipe_id │ │ food_id  │
       │ user_id   │ │ amount       │ │ food_id   │ │ meal_id  │
       └───────────┘ └──────────────┘ │ quantity  │ │ quantity │
       (standard +   (junction table) │ unit      │ │ time     │
        custom)                        └───────────┘ └──────────┘
                                       (clean PK)
```

**Key Design Principles:**
- **Flexible Goals:** Track any metric (calories, sat fat, WW points) via key-value
- **Flexible Nutrients:** Foods store only available nutrients (1-30+)
- **Meal Categories:** Standard meals + user-defined custom meals
- **Normalized:** No NULL columns, proper relational design

### Tables

#### **users**
User accounts for authentication and data ownership.

| Column         | Type          | Constraints        | Description                    |
|:---------------|:--------------|:-------------------|:-------------------------------|
| id             | INTEGER       | PRIMARY KEY        | Auto-incrementing user ID      |
| username       | VARCHAR(50)   | UNIQUE, NOT NULL   | Unique username                |
| email          | VARCHAR(255)  | UNIQUE, NOT NULL   | User email address             |
| password_hash  | VARCHAR(255)  | NOT NULL           | Bcrypt hashed password         |
| created_at     | DATETIME      | NOT NULL           | Account creation timestamp     |
| updated_at     | DATETIME      | NOT NULL           | Last update timestamp          |

**Indexes:** username, email

---

#### **nutrients**
Defines available nutrients (standard and user-defined).

| Column             | Type          | Constraints          | Description                          |
|:-------------------|:--------------|:---------------------|:-------------------------------------|
| id                 | INTEGER       | PRIMARY KEY          | Auto-incrementing nutrient ID        |
| name               | VARCHAR(100)  | NOT NULL             | Nutrient name (e.g., "Calories")    |
| unit               | VARCHAR(20)   | NOT NULL             | Unit (e.g., "kcal", "g", "points")  |
| description        | TEXT          | NULL                 | Nutrient description                 |
| created_by_user_id | INTEGER       | NULL                 | NULL = standard, set = user-defined  |
| created_at         | DATETIME      | NOT NULL             | Creation timestamp                   |
| updated_at         | DATETIME      | NOT NULL             | Last update timestamp                |

**Standard Nutrients (18):** Calories, Protein, Carbs, Fat, Fiber, Sugars, Sat Fat, Trans Fat, Sodium, Cholesterol, Vitamins (A, C, D), Minerals (Calcium, Iron, Potassium)

**Custom Nutrients:** Users can add Weight Watchers Points, Net Carbs, etc.

---

#### **foods**
Food items from USDA database or user-created custom foods.

| Column             | Type          | Constraints                | Description                              |
|:-------------------|:--------------|:---------------------------|:-----------------------------------------|
| id                 | INTEGER       | PRIMARY KEY                | Auto-incrementing food ID                |
| name               | VARCHAR(255)  | NOT NULL                   | Food name (e.g., "Chicken Breast")      |
| brand              | VARCHAR(255)  | NULL                       | Brand name for branded foods             |
| serving_size       | NUMERIC(10,2) | NOT NULL                   | Serving size quantity                    |
| unit               | VARCHAR(50)   | NOT NULL                   | Serving unit (g, oz, cup, etc.)          |
| usda_fdc_id        | INTEGER       | UNIQUE, NULL               | USDA FoodData Central ID (if USDA food)  |
| created_by_user_id | INTEGER       | FK → users.id, NULL        | User who created (null for USDA foods)   |
| notes              | TEXT          | NULL                       | Additional food notes                    |
| created_at         | DATETIME      | NOT NULL                   | Creation timestamp                       |
| updated_at         | DATETIME      | NOT NULL                   | Last update timestamp                    |

**Indexes:**
- GIN index on `name` using pg_trgm (for fuzzy search)
- Composite index on `(brand, name)`
- Index on `created_by_user_id`
- Unique index on `usda_fdc_id`

**Key Features:**
- **Flexible Nutrients:** Actual nutrient values stored in `food_nutrients` table
- **USDA Integration:** Foods with `usda_fdc_id` set are from USDA database
- **Custom Foods:** Users can create custom foods (sets `created_by_user_id`)
- **Fuzzy Search:** GIN index enables fast similarity searches like "chiken" → "chicken"

---

#### **food_nutrients**
Nutrient values for foods (junction table).

| Column             | Type          | Constraints                    | Description                        |
|:-------------------|:--------------|:-------------------------------|:-----------------------------------|
| id                 | INTEGER       | PRIMARY KEY                    | Auto-incrementing ID               |
| food_id            | INTEGER       | FK → foods.id, NOT NULL        | Food item                          |
| nutrient_id        | INTEGER       | FK → nutrients.id, NOT NULL    | Nutrient type                      |
| amount_per_serving | NUMERIC(10,2) | NOT NULL                       | Amount per serving                 |
| created_at         | DATETIME      | NOT NULL                       | Creation timestamp                 |
| updated_at         | DATETIME      | NOT NULL                       | Last update timestamp              |

**Constraints:**
- Unique constraint on `(food_id, nutrient_id)` - each food can have each nutrient only once
- Composite index on `(food_id, nutrient_id)` for efficient queries

**Benefits:**
- USDA foods can have 30+ nutrients, custom foods can have just 1
- No NULL columns for missing nutrients
- Easily extensible without schema changes

---

#### **meals**
Meal categories for organizing food logs.

| Column             | Type         | Constraints                | Description                          |
|:-------------------|:-------------|:---------------------------|:-------------------------------------|
| id                 | INTEGER      | PRIMARY KEY                | Auto-incrementing meal ID            |
| name               | VARCHAR(100) | NOT NULL                   | Meal name (e.g., "Breakfast")       |
| created_by_user_id | INTEGER      | FK → users.id, NULL        | NULL = standard, set = user-defined  |
| display_order      | INTEGER      | NOT NULL, DEFAULT 999      | Display order in UI                  |
| created_at         | DATETIME     | NOT NULL                   | Creation timestamp                   |
| updated_at         | DATETIME     | NOT NULL                   | Last update timestamp                |

**Standard Meals (4):** Breakfast, Lunch, Dinner, Snack

**Custom Meals:** Users can add Brunch, Pre-Workout, Tea Time, etc.

---

#### **food_logs**
Daily food consumption records organized by meal.

| Column      | Type          | Constraints                | Description                          |
|:------------|:--------------|:---------------------------|:-------------------------------------|
| id          | INTEGER       | PRIMARY KEY                | Auto-incrementing log ID             |
| user_id     | INTEGER       | FK → users.id, NOT NULL    | User who logged the food             |
| food_id     | INTEGER       | FK → foods.id, NOT NULL    | Food that was consumed               |
| meal_id     | INTEGER       | FK → meals.id, NULL        | Meal category (breakfast, lunch...)  |
| quantity    | NUMERIC(10,2) | NOT NULL                   | Quantity in food's serving units     |
| logged_at   | DATETIME      | NOT NULL                   | When food was consumed               |
| notes       | TEXT          | NULL                       | Optional notes                       |
| created_at  | DATETIME      | NOT NULL                   | Record creation timestamp            |
| updated_at  | DATETIME      | NOT NULL                   | Last update timestamp                |

**Indexes:**
- Composite index on `(user_id, logged_at)` for efficient daily queries
- Index on `meal_id` for meal-based queries

**Foreign Key Behavior:**
- `user_id`: CASCADE (delete logs when user deleted)
- `food_id`: RESTRICT (prevent deleting foods that are logged)
- `meal_id`: SET NULL (preserve log if meal deleted)

---

#### **recipes**
User-created recipes composed of multiple ingredients.

| Column      | Type         | Constraints                | Description                    |
|:------------|:-------------|:---------------------------|:-------------------------------|
| id          | INTEGER      | PRIMARY KEY                | Auto-incrementing recipe ID    |
| user_id     | INTEGER      | FK → users.id, NOT NULL    | Recipe owner                   |
| name        | VARCHAR(255) | NOT NULL                   | Recipe name                    |
| description | TEXT         | NULL                       | Recipe instructions/notes      |
| created_at  | DATETIME     | NOT NULL                   | Creation timestamp             |
| updated_at  | DATETIME     | NOT NULL                   | Last update timestamp          |

**Indexes:** user_id

---

#### **recipe_ingredients**
Many-to-many relationship between recipes and foods with quantities.

| Column               | Type          | Constraints                     | Description                         |
|:---------------------|:--------------|:--------------------------------|:------------------------------------|
| recipe_ingredient_id | INTEGER       | PRIMARY KEY                     | Auto-incrementing ID (also order)   |
| recipe_id            | INTEGER       | FK → recipes.id, NOT NULL       | Parent recipe                       |
| food_id              | INTEGER       | FK → foods.id, NOT NULL         | Ingredient food item                |
| quantity             | NUMERIC(10,2) | NOT NULL                        | Ingredient quantity                 |
| unit                 | VARCHAR(50)   | NOT NULL                        | Quantity unit                       |
| created_at  | DATETIME      | NOT NULL                        | Creation timestamp                  |
| updated_at  | DATETIME      | NOT NULL                        | Last update timestamp               |

**Indexes:** recipe_id, food_id

**Foreign Key Behavior:**
- `recipe_id`: CASCADE (delete ingredients when recipe deleted)
- `food_id`: RESTRICT (prevent deleting foods used in recipes)

---

#### **user_goals**
Daily nutrition targets (flexible key-value structure).

| Column       | Type          | Constraints                | Description                           |
|:-------------|:--------------|:---------------------------|:--------------------------------------|
| id           | INTEGER       | PRIMARY KEY                | Auto-incrementing goal ID             |
| user_id      | INTEGER       | FK → users.id, NOT NULL    | User who owns this goal               |
| goal_type    | VARCHAR(100)  | NOT NULL                   | Goal type (e.g., "calories", "ww_points") |
| target_value | NUMERIC(10,2) | NOT NULL                   | Target value                          |
| unit         | VARCHAR(20)   | NULL                       | Unit (e.g., "kcal", "g", "points")   |
| created_at   | DATETIME      | NOT NULL                   | Creation timestamp                    |
| updated_at   | DATETIME      | NOT NULL                   | Last update timestamp                 |

**Constraints:**
- Unique constraint on `(user_id, goal_type)` - each user can have each goal type only once

**Examples:**
```
user_id | goal_type           | target_value | unit
--------|---------------------|--------------|------
1       | calories            | 2000         | kcal
1       | protein_g           | 150          | g
1       | saturated_fat_g     | 20           | g
2       | ww_points           | 23           | points
```

**Benefits:**
- Track ANY goal type without schema changes
- Users only store goals they care about
- Supports macros, micronutrients, Weight Watchers, keto net carbs, etc.

---

### Implementation Details

#### Technology
- **ORM:** SQLAlchemy 2.0 (async)
- **Driver:** asyncpg (PostgreSQL async driver)
- **Migrations:** Alembic (async-enabled)
- **Type Safety:** Full type hints using `Mapped[type]` annotations
- **Tables:** 9 tables (users, nutrients, foods, food_nutrients, meals, food_logs, recipes, recipe_ingredients, user_goals)

#### Key Features
- **Flexible Schema:** Goals, nutrients, and meals stored as data (not hardcoded columns)
- **Async-First:** All database operations use `async/await`
- **Auto Timestamps:** All tables have `created_at` and `updated_at` managed automatically
- **Decimal Precision:** All nutrition values use `NUMERIC(10,2)` to avoid floating-point errors
- **Fuzzy Search:** pg_trgm extension enables typo-tolerant food search (GIN indexes)
- **Normalized Design:** No NULL columns, proper relational structure
- **Efficient Queries:** Composite indexes for common access patterns
- **Data Integrity:** Foreign keys with appropriate CASCADE/RESTRICT behavior
- **Multi-tenancy:** All user data scoped by `user_id` foreign keys
- **Extensible:** Add new nutrients, goals, or meals without schema migrations

#### Standard Data
The system includes seeded standard data:
- **18 Standard Nutrients:** Calories, Protein, Carbs, Fat, Fiber, Sugars, Saturated Fat, Trans Fat, Sodium, Cholesterol, Potassium, Vitamins (A, C, D), Minerals (Calcium, Iron)
- **4 Standard Meals:** Breakfast, Lunch, Dinner, Snack
- Users can add custom nutrients and meals as needed

#### Files
- **Models:** `whati8/models/*.py` (9 model files)
  - `base.py`, `user.py`, `nutrient.py`, `food.py`, `food_nutrient.py`
  - `meal.py`, `food_log.py`, `recipe.py`, `user_goal.py`
- **Configuration:** `whati8/config.py` (Pydantic Settings)
- **Database:** `whati8/database.py` (async engine + session factory)
- **Migrations:** `alembic/versions/` (Alembic migrations)
- **Seeds:** `scripts/seed_standard_data.py` (standard nutrients and meals)

#### Usage Examples

**Fuzzy Food Search:**
```python
from whati8.models import Food
from sqlalchemy import select, func

# Typo-tolerant search: "chiken" → "chicken"
result = await db.execute(
    select(Food)
    .where(func.similarity(Food.name, "chiken") > 0.3)
    .order_by(func.similarity(Food.name, "chiken").desc())
    .limit(20)
)
foods = result.scalars().all()
```

**Create Food with Nutrients:**
```python
from whati8.models import Food, FoodNutrient, Nutrient

# Get standard nutrients
nutrients = await db.execute(
    select(Nutrient).where(Nutrient.name.in_(["Calories", "Protein"]))
)
nutrient_map = {n.name: n.id for n in nutrients.scalars()}

# Create food
food = Food(name="Chicken Breast", serving_size=100, unit="g")
db.add(food)
await db.flush()

# Add nutrients
food.food_nutrients.extend([
    FoodNutrient(nutrient_id=nutrient_map["Calories"], amount_per_serving=165),
    FoodNutrient(nutrient_id=nutrient_map["Protein"], amount_per_serving=31),
])
await db.commit()
```

**Set Flexible User Goals:**
```python
from whati8.models import UserGoal

# User tracks calories and saturated fat
goals = [
    UserGoal(user_id=1, goal_type="calories", target_value=2000, unit="kcal"),
    UserGoal(user_id=1, goal_type="saturated_fat_g", target_value=20, unit="g"),
]
db.add_all(goals)
await db.commit()
```

**Log Food to Meal:**
```python
from whati8.models import FoodLog, Meal

# Get breakfast meal
breakfast = await db.scalar(
    select(Meal).where(Meal.name == "Breakfast")
)

# Log food
log = FoodLog(
    user_id=1,
    food_id=food_id,
    meal_id=breakfast.id,
    quantity=1.5,
    logged_at=datetime.now(),
)
db.add(log)
await db.commit()
```

---

## Roadmap & Next Steps

See **[ROADMAP.md](ROADMAP.md)** for the full roadmap.

**Current phase:** Phase 3 — Dashboard & Analytics (daily nutrition views, goal/meal/recipe CRUD, visualizations).

## Architecture

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for system design, data flow, and key design decisions.
