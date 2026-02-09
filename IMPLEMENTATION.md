# whati8 Implementation Guide

Complete developer guide for the whati8 nutrition tracker implementation.

## Table of Contents
- [Current Status](#current-status)
- [Architecture Overview](#architecture-overview)
- [Schema Design](#schema-design)
- [Authentication System](#authentication-system)
- [Setup Instructions](#setup-instructions)
- [Usage Examples](#usage-examples)
- [API Reference](#api-reference)
- [Next Steps](#next-steps)

---

## Current Status

### ✅ Completed (Phase 1)

**Infrastructure & Database**
- ✅ Project structure with proper Python package hierarchy
- ✅ Configuration layer (Pydantic Settings with .env)
- ✅ Async database connection (SQLAlchemy 2.0 + asyncpg)
- ✅ Alembic migrations (async-enabled)
- ✅ Setup automation scripts (database, seeding, verification)

**Domain Model (9 Tables)**
- ✅ Flexible schema design (goals, nutrients, meals as data, not columns)
- ✅ All models with full type hints and async support
- ✅ Standard data seeding (18 nutrients, 4 meals)
- ✅ GIN indexes for fuzzy text search (pg_trgm)
- ✅ Proper foreign keys with CASCADE/RESTRICT

**Authentication System**
- ✅ Pydantic schemas (UserCreate, Token, UserResponse, etc.)
- ✅ Auth service layer (password hashing, JWT tokens, user CRUD)
- ✅ CLI commands (register, login, whoami)
- ✅ bcrypt password hashing
- ✅ JWT token management with python-jose
- ✅ Database migrations with users table
- ✅ REST API endpoints (register, login, /me)
- ✅ FastAPI app with exception handlers and CORS
- ✅ Bearer token authentication with dependency injection
- ✅ OpenAPI documentation (Swagger UI + ReDoc)
- ✅ LAN-accessible development server

**USDA Data Import System**
- ✅ Bulk download from USDA FoodData Central (Foundation Foods + SR Legacy)
- ✅ Automated ZIP download and JSON extraction
- ✅ USDA nutrient ID mapping to standard nutrients
- ✅ 8,058 foods imported with 130,633 nutrient relationships
- ✅ CLI command: `uv run python -m whati8 import-usda`
- ✅ Progress tracking with batch processing (100 foods/batch)
- ✅ Data cached locally (~219 MB total)

**Food Search API**
- ✅ Pydantic schemas (FoodResponse, FoodSearchResultItem, FoodSearchResponse)
- ✅ GET /foods/search - Fuzzy text search with pg_trgm
- ✅ GET /foods/{id} - Detailed food with all nutrients
- ✅ Typo-tolerant search ("chiken" → "chicken")
- ✅ Similarity scoring (0-1 range, higher = better match)
- ✅ Pagination support (limit, offset)
- ✅ Authentication required on all endpoints
- ✅ Key nutrient preview in search results (calories, protein, carbs, fat)
- ✅ Complete nutrient data in detail endpoint

**AI Food Resolution System**
- ✅ Natural language food parsing with Claude AI
- ✅ Pydantic schemas (FoodResolveRequest, ParsedFoodItem, FoodMatchOption, ResolvedFoodItem, FoodResolveResponse)
- ✅ POST /foods/resolve - Parse text like "I had 2 eggs and toast for breakfast"
- ✅ Tool calling for structured JSON extraction (quantity, unit, food name, confidence)
- ✅ Automatic database matching with fuzzy search
- ✅ Meal context detection (breakfast, lunch, dinner, snack)
- ✅ Multi-option matching for user confirmation (top 3 matches per item)
- ✅ Confidence scoring (0.0-1.0) based on input clarity
- ✅ Comprehensive error handling (invalid input, API failures, rate limits)
- ✅ Configurable model via ANTHROPIC_MODEL env var
- ✅ Requires ANTHROPIC_API_KEY in environment
- ✅ Cost: ~$0.001-0.003 per resolution request

**Food Logging API**
- ✅ Complete CRUD operations for food logs
- ✅ Pydantic schemas (FoodLogCreate, FoodLogUpdate, FoodLogResponse, FoodLogListResponse)
- ✅ POST /logs - Create food log with validation
- ✅ GET /logs - List logs with date/meal filtering and pagination
- ✅ GET /logs/{id} - Get single log with full details
- ✅ PUT /logs/{id} - Update log (all fields optional)
- ✅ DELETE /logs/{id} - Delete log (204 No Content)
- ✅ Authorization enforcement (users only see their own logs)
- ✅ Query efficiency (no N+1 problems with eager loading)
- ✅ Full food details with nutrients in all responses
- ✅ Date filtering (YYYY-MM-DD format)
- ✅ Meal category filtering
- ✅ Pagination (50 default, 200 max)
- ✅ Comprehensive test suite (13 tests, all passing)

**Conversational Agent UI** ⭐ *PRODUCTION READY*
- ✅ Multi-turn tool calling with Claude API
- ✅ Agent service with conversation management (60-min expiration)
- ✅ POST /agent/chat endpoint (rate limited 5/min)
- ✅ 7 tools: log_food, search_foods, resolve_foods_nl, list_logs, get_daily_summary, delete_log, show_confirmation_form
- ✅ Svelte frontend with Tailwind CSS
- ✅ Mobile-first responsive chat interface
- ✅ User authentication with JWT (registration + login)
- ✅ Real-time message display with loading states
- ✅ Food selection modals with nutrition info
- ✅ Local timestamps (all messages display in user's local time)
- ✅ Smart deduplication (prefers human-readable portions like "69g/fruit" over "100g")
- ✅ Static file serving (single-server deployment)
- ✅ Production build working
- ✅ All known issues resolved (Feb 8, 2026 evening)

### ⏭️ Next Steps

1. **Dashboard API** (HIGH PRIORITY)
   - GET /dashboard/today - Daily nutrition summary
   - GET /dashboard/week - Weekly trends
   - Aggregate nutrients from food logs
   - Compare actual vs. goal values
   - Show trends over time

2. **Goal Management API** - CRUD endpoints for flexible nutrition goals
   - POST /goals - Create user goal
   - GET /goals - List user's goals
   - PUT /goals/{id} - Update goal
   - DELETE /goals/{id} - Delete goal

3. **Recipe Management API** - CRUD endpoints for user recipes
   - POST /recipes - Create recipe with ingredients
   - GET /recipes - List user's recipes
   - PUT /recipes/{id} - Update recipe
   - DELETE /recipes/{id} - Delete recipe

4. **Conversation Persistence** - Move from in-memory to database storage

5. **AI Enhancements** (Future)
   - Photo upload support with Claude Vision
   - Streaming responses (SSE)
   - Voice input (Web Speech API)
   - Recipe/dish detection ("chicken parmesan" → multiple ingredients)

---

## Architecture Overview

### Technology Stack

| Component | Technology | Notes |
|:----------|:-----------|:------|
| **Backend** | Python 3.10+, FastAPI | High-performance async API |
| **Frontend** | Svelte 4, Vite 5, TypeScript | Reactive UI with SPA routing |
| **Styling** | Tailwind CSS 3 | Utility-first, mobile-first design |
| **Database** | PostgreSQL 14+, SQLAlchemy 2.0 | Async ORM with full type safety |
| **Driver** | asyncpg | High-performance PostgreSQL driver |
| **Migrations** | Alembic | Async-enabled schema versioning |
| **Validation** | Pydantic v2 | Request/response schemas |
| **Auth** | JWT (python-jose), bcrypt (passlib) | Secure token-based auth |
| **AI/LLM** | Anthropic Claude Sonnet 4.5 | Natural language food parsing & agent |
| **Data Source** | USDA Food Data Central API | 50,000+ foods with nutrients |

### Package Structure

```
whati8/
├── __init__.py
├── config.py              # Pydantic Settings configuration
├── database.py            # Async SQLAlchemy engine and session
├── models/                # SQLAlchemy ORM models (9 models)
│   ├── __init__.py
│   ├── base.py            # Base class + TimestampMixin
│   ├── user.py            # User accounts
│   ├── nutrient.py        # Nutrient definitions
│   ├── food.py            # Food items
│   ├── food_nutrient.py   # Food ↔ Nutrient junction
│   ├── meal.py            # Meal categories
│   ├── food_log.py        # Daily consumption logs
│   ├── recipe.py          # User recipes + ingredients
│   └── user_goal.py       # Flexible user goals
├── schemas/               # Pydantic request/response schemas
│   ├── auth.py            # Auth schemas (UserCreate, Token, etc.)
│   └── food.py            # Food schemas (FoodResponse, FoodSearchResult, etc.)
├── services/              # Business logic layer
│   └── auth.py            # Authentication service
├── api/                   # FastAPI application
│   ├── __init__.py        # Export app instance
│   ├── app.py             # FastAPI app factory
│   ├── deps.py            # Shared dependencies (auth, db)
│   ├── exceptions.py      # Exception handlers
│   └── routers/           # API route modules
│       ├── __init__.py
│       ├── auth.py        # Auth endpoints
│       └── food.py        # Food search endpoints
└── cli/                   # CLI commands
    ├── __init__.py        # CLI entry + serve command
    └── auth.py            # Auth CLI (register, login, whoami)
```

### Design Principles

1. **Async-First**: All database operations use `async/await` for scalability
2. **Type Safety**: Full type hints with SQLAlchemy 2.0 `Mapped[type]` and Pydantic
3. **Service Layer Pattern**: Business logic in services, reusable from CLI or API
4. **Flexible Schema**: Goals, nutrients, meals stored as data (not hardcoded columns)
5. **Separation of Concerns**: Clean layers (models, schemas, services, routes, CLI)

---

## Schema Design

### Database Tables (9 Total)

#### Core Tables

**users** - User accounts
- `id`, `username` (unique), `email` (unique), `password_hash`
- Indexes on username and email

**foods** - Food items (USDA + user-created)
- `id`, `name`, `brand`, `serving_size`, `unit`
- `usda_fdc_id` (nullable, for USDA foods)
- `created_by_user_id` (nullable, for user-created foods)
- GIN index on `name` for fuzzy search (pg_trgm)

**food_logs** - Daily consumption records
- `id`, `user_id`, `food_id`, `meal_id`, `quantity`, `logged_at`
- Composite index on `(user_id, logged_at)` for efficient queries

**recipes** - User-created recipes
- `id`, `user_id`, `name`, `description`

**recipe_ingredients** - Recipe composition
- `recipe_ingredient_id` (serves as both PK and display order)
- `recipe_id`, `food_id`, `quantity`, `unit`

#### Flexible Design Tables

**nutrients** - Nutrient definitions (standard + user-defined)
- Standard: Calories, Protein, Carbs, Fat, Fiber, Vitamins, etc. (18 total)
- Custom: Users can add WW Points, Net Carbs, etc.
- `created_by_user_id` = NULL for standard, set for user-defined

**food_nutrients** - Food ↔ Nutrient junction table
- `food_id`, `nutrient_id`, `amount_per_serving`
- Unique constraint on `(food_id, nutrient_id)`
- **Benefit**: Foods can have 1-30+ nutrients based on available data

**meals** - Meal categories (standard + user-defined)
- Standard: Breakfast, Lunch, Dinner, Snack
- Custom: Users can add Brunch, Pre-Workout, etc.
- `created_by_user_id` = NULL for standard, set for user-defined

**user_goals** - Flexible user nutrition goals (key-value)
- `user_id`, `goal_type`, `target_value`, `unit`
- Unique constraint on `(user_id, goal_type)`
- **Benefit**: Track ANY goal (calories, sat fat, WW points) without schema changes

### Why This Design?

#### Before (Inflexible)
```sql
-- ❌ Hardcoded columns, can't track other metrics
CREATE TABLE foods (
    calories_per_serving NUMERIC,
    protein_g NUMERIC,
    carbs_g NUMERIC,
    fat_g NUMERIC,
    fiber_g NUMERIC,
    sugar_g NUMERIC
);

-- ❌ Fixed goals, can't track WW points or custom metrics
CREATE TABLE user_goals (
    daily_calories_target NUMERIC,
    daily_protein_g NUMERIC,
    daily_carbs_g NUMERIC,
    daily_fat_g NUMERIC
);
```

#### After (Flexible)
```sql
-- ✅ Flexible: foods have only available nutrients
CREATE TABLE food_nutrients (
    food_id INTEGER,
    nutrient_id INTEGER,
    amount_per_serving NUMERIC,
    UNIQUE(food_id, nutrient_id)
);

-- ✅ Flexible: track any goal type
CREATE TABLE user_goals (
    user_id INTEGER,
    goal_type VARCHAR(100),  -- "calories", "ww_points", "saturated_fat_g", etc.
    target_value NUMERIC,
    unit VARCHAR(20),
    UNIQUE(user_id, goal_type)
);
```

**Benefits:**
- USDA foods can have 30+ nutrients, user foods can have just 1
- Track ANY metric (calories, macros, WW points, net carbs) without migrations
- Users only store goals they care about (no NULL columns)
- Extensible without schema changes

### Standard Data

**18 Standard Nutrients** (seeded automatically):
- Macros: Calories, Protein, Total Carbohydrates, Total Fat
- Fiber & Sugar: Dietary Fiber, Total Sugars
- Fat Breakdown: Saturated Fat, Trans Fat, Monounsaturated Fat, Polyunsaturated Fat
- Electrolytes: Sodium, Potassium, Cholesterol
- Vitamins: A, C, D
- Minerals: Calcium, Iron

**4 Standard Meals** (seeded automatically):
1. Breakfast (display_order=1)
2. Lunch (display_order=2)
3. Dinner (display_order=3)
4. Snack (display_order=4)

---

## Authentication System

### Overview

Complete authentication system with:
- **Service Layer**: Reusable business logic for password hashing, JWT tokens, user CRUD
- **CLI Commands**: register, login, whoami for terminal usage
- **REST API**: FastAPI endpoints with OpenAPI documentation
- **Security**: HTTPBearer token authentication with dependency injection

### Components

#### 1. Pydantic Schemas (`whati8/schemas/auth.py`)

```python
class UserCreate(BaseModel):
    """Registration schema with validation."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)

class UserLogin(BaseModel):
    """Login schema (username OR email)."""
    login: str  # Can be username or email
    password: str

class UserResponse(BaseModel):
    """Safe user response (no password)."""
    id: int
    username: str
    email: str
    created_at: datetime

class Token(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenPayload(BaseModel):
    """JWT payload validation."""
    sub: int  # User ID
    exp: int  # Expiration timestamp
```

#### 2. Authentication Service (`whati8/services/auth.py`)

**Core Functions:**
- `hash_password(password: str) -> str` - bcrypt hashing
- `verify_password(plain_password: str, hashed_password: str) -> bool`
- `create_access_token(user_id: int) -> str` - Generate JWT token
- `decode_token(token: str) -> TokenPayload` - Validate and decode JWT
- `create_user(db: AsyncSession, user_data: UserCreate) -> User`
- `get_user_by_login(db: AsyncSession, login: str) -> User | None`
- `get_user_by_id(db: AsyncSession, user_id: int) -> User | None`
- `authenticate_user(db: AsyncSession, login: str, password: str) -> User | None`

**Features:**
- All functions are static methods (pure, stateless)
- Async/await throughout
- Full type hints
- Flexible login (username OR email)

#### 3. CLI Commands (`whati8/cli/auth.py`)

```bash
# Register new user
uv run python -m whati8 auth register
# Prompts: username, email, password, confirmation

# Login and get JWT token
uv run python -m whati8 auth login
# Prompts: username/email, password
# Returns: JWT token with expiration

# Validate token and show user
uv run python -m whati8 auth whoami <token>
# Returns: user info and token expiration
```

### Security Features

- ✅ **Password Hashing**: bcrypt with 12 rounds (secure default)
- ✅ **No Plain Passwords**: Never stored or logged
- ✅ **JWT Tokens**: HS256 algorithm with 24-hour expiration (configurable)
- ✅ **JWT Secret**: Minimum 32 characters required
- ✅ **Flexible Login**: Username OR email accepted
- ✅ **Safe Responses**: `password_hash` never returned to client
- ✅ **Database Constraints**: Unique username and email enforced
- ✅ **JWT Spec Compliance**: Subject claim as string, converted to int internally

### REST API Implementation

**FastAPI application with modular architecture** (`whati8/api/`):

#### App Structure
- `app.py` - FastAPI factory with CORS, exception handlers, routers
- `deps.py` - Shared dependencies (authentication, database)
- `exceptions.py` - Exception handlers (HTTPException, JWTError, IntegrityError)
- `routers/auth.py` - Authentication endpoints

#### Endpoints

**POST /auth/register** (201 Created)
- Body: `{"username": "user", "email": "user@example.com", "password": "password123"}`
- Returns: User object (without password)
- Errors: 409 (duplicate), 422 (validation)

**POST /auth/login** (200 OK)
- Body: `{"login": "user", "password": "password123"}`
- Returns: `{"access_token": "...", "token_type": "bearer", "expires_in": 86400}`
- Errors: 401 (invalid credentials), 422 (validation)

**GET /auth/me** (200 OK)
- Header: `Authorization: Bearer <token>`
- Returns: Current user object
- Errors: 401 (invalid token), 404 (user not found)

#### Starting the Server

```bash
# Development server with auto-reload (LAN-accessible)
uv run python -m whati8 serve --reload

# Access from any LAN device:
# - Swagger UI: http://192.168.1.11:8000/docs
# - ReDoc: http://192.168.1.11:8000/redoc
# - From server: http://localhost:8000/docs

# Custom host/port
uv run python -m whati8 serve --host 0.0.0.0 --port 8080 --reload
```

#### Testing the API

```bash
# Automated test script (from any LAN device)
./scripts/test_api.sh

# Or manually with curl:
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","email":"test@example.com","password":"password123"}'

# Login
TOKEN=$(curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"login":"testuser","password":"password123"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# Get current user
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

#### Security Features

- **HTTPBearer** authentication scheme
- **Dependency injection** for protected endpoints
- **Exception handlers** for consistent error responses
- **CORS** enabled for frontend development
- **OpenAPI** documentation with security schemes
- **Validation** via Pydantic schemas

---

## USDA Data Import System

### Overview

Automated import system for USDA Food Data Central bulk datasets. Downloads, parses, and imports foods with complete nutrient profiles.

### Components

**1. Import Script** (`scripts/import_usda_data.py`)

Main import orchestrator that handles:
- Bulk file download from USDA FDC
- ZIP extraction and JSON parsing
- Nutrient ID mapping (USDA → our database)
- Batch insertion with progress tracking
- Error handling and statistics

**2. CLI Command** (`whati8/cli/__init__.py`)

```bash
# Full import (~8,000 foods)
uv run python -m whati8 import-usda

# Test import (limit to N foods per dataset)
uv run python -m whati8 import-usda --limit 100
```

**3. Data Sources**

| Dataset | Foods | Size (Compressed) | Size (Uncompressed) |
|---------|-------|-------------------|---------------------|
| Foundation Foods | 245 | 409 KB | 5.5 MB |
| SR Legacy | 7,793 | 12 MB | 201 MB |
| **Total Imported** | **8,038** | **~12.5 MB** | **~206 MB** |

**Note:** Branded Foods database (400,000+ foods, 3.1 GB) not imported by default.

### Nutrient Mapping

The importer maps USDA nutrient IDs to our standard nutrients:

```python
NUTRIENT_MAPPING = {
    1008: "Calories",              # Energy
    1003: "Protein",
    1005: "Total Carbohydrates",   # Carbohydrate
    1004: "Total Fat",
    1079: "Dietary Fiber",         # Fiber
    2000: "Total Sugars",          # Total Sugar
    1258: "Saturated Fat",
    1257: "Trans Fat",
    1292: "Monounsaturated Fat",
    1293: "Polyunsaturated Fat",
    1093: "Sodium",
    1253: "Cholesterol",
    1092: "Potassium",
    1106: "Vitamin A",
    1162: "Vitamin C",
    1114: "Vitamin D",
    1087: "Calcium",
    1089: "Iron",
}
```

### Import Statistics

**Final Database:**
- 8,058 foods
- 130,633 nutrient relationships
- 16.2 average nutrients per food
- ~30 seconds import time

### File Structure

**Downloaded Files (cached in `data/usda/`):**
```
data/usda/
├── FoodData_Central_foundation_food_json_2023-10-26.zip
├── FoodData_Central_foundation_food_json_2023-10-26/
│   └── foundationDownload.json (5.5 MB)
├── FoodData_Central_sr_legacy_food_json_2021-10-28.zip
└── FoodData_Central_sr_legacy_food_json_2021-10-28/
    └── FoodData_Central_sr_legacy_food_json_2021-10-28.json (201 MB)
```

---

## Food Search API

### Overview

RESTful API for searching foods with fuzzy text matching and retrieving detailed nutrition information.

### Components

**1. Pydantic Schemas** (`whati8/schemas/food.py`)

```python
class NutrientResponse(BaseModel):
    """Nutrient information."""
    id: int
    name: str
    unit: str
    description: str | None

class FoodNutrientResponse(BaseModel):
    """Nutrient amount in a food."""
    nutrient: NutrientResponse
    amount_per_serving: float

class FoodResponse(BaseModel):
    """Complete food with all nutrients."""
    id: int
    name: str
    brand: str | None
    serving_size: float
    unit: str
    usda_fdc_id: int | None
    food_nutrients: list[FoodNutrientResponse]
    # ... timestamps, notes, etc.

class FoodSearchResultItem(BaseModel):
    """Search result with key nutrients preview."""
    id: int
    name: str
    brand: str | None
    serving_size: float
    unit: str
    similarity: float  # 0-1 similarity score
    # Key nutrients for preview
    calories: float | None
    protein: float | None
    carbs: float | None
    fat: float | None

class FoodSearchResponse(BaseModel):
    """Paginated search results."""
    query: str
    results: list[FoodSearchResultItem]
    total: int
    limit: int
    offset: int
```

**2. API Router** (`whati8/api/routers/food.py`)

Two main endpoints:

**GET /foods/search** - Fuzzy food search
- Query parameter: `q` (min 2 characters)
- Optional: `limit` (1-100, default 20), `offset` (default 0)
- Uses PostgreSQL `pg_trgm` for typo-tolerance
- Returns similarity scores (0-1, higher = better match)
- Includes key nutrient preview
- Authentication required

**GET /foods/{id}** - Food details
- Path parameter: `food_id`
- Returns complete food with all nutrients
- Eager-loads relationships for performance
- Authentication required

### Search Algorithm

Uses PostgreSQL's **pg_trgm extension** for trigram-based similarity:

```python
# Similarity threshold (0.1 = broad matching)
similarity_threshold = 0.1

# Query with similarity scoring
query = (
    select(Food, func.similarity(Food.name, search_term).label("score"))
    .where(func.similarity(Food.name, search_term) > similarity_threshold)
    .order_by(func.similarity(Food.name, search_term).desc())
)
```

**Example:** Search for "chiken" (typo)
- Still finds "Chicken, broilers or fryers..."
- Similarity score: 0.36 (lower than exact match, but above threshold)
- Results ranked by similarity

### Testing the API

**Automated Test Script:**
```bash
./scripts/test_food_api.sh
```

Tests:
- ✅ User authentication
- ✅ Exact search ("chicken")
- ✅ Fuzzy search with typos ("chiken", "brocoli")
- ✅ Food detail retrieval
- ✅ Authentication enforcement

**Manual Testing with curl:**
```bash
# 1. Login
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"login":"foodtester","password":"password123"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# 2. Search foods (typo-tolerant!)
curl "http://localhost:8000/foods/search?q=chiken&limit=5" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 3. Get food details
curl "http://localhost:8000/foods/102" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**Using Swagger UI:**
1. Start server: `uv run python -m whati8 serve --reload`
2. Open: http://localhost:8000/docs
3. Authorize with JWT token
4. Try the `/foods/search` and `/foods/{id}` endpoints

### Performance Considerations

**Search Optimization:**
- GIN index on `food.name` for fast trigram matching
- Batch nutrient queries (one query per search, not per food)
- Nutrient map caching within request

**Detail Endpoint:**
- Eager loading with `selectinload()` to avoid N+1 queries
- Single database round-trip for food + all nutrients

### Example Responses

**Search Response:**
```json
{
  "query": "chicken",
  "results": [
    {
      "id": 6318,
      "name": "Fat, chicken",
      "brand": null,
      "serving_size": 205.0,
      "unit": "g",
      "usda_fdc_id": 173564,
      "similarity": 0.67,
      "calories": 900.0,
      "protein": 0.0,
      "carbs": 0.0,
      "fat": 99.8
    }
  ],
  "total": 446,
  "limit": 5,
  "offset": 0
}
```

**Food Detail Response:**
```json
{
  "id": 6318,
  "name": "Fat, chicken",
  "serving_size": 205.0,
  "unit": "g",
  "usda_fdc_id": 173564,
  "food_nutrients": [
    {
      "nutrient": {
        "id": 1,
        "name": "Calories",
        "unit": "kcal"
      },
      "amount_per_serving": 900.0
    },
    // ... 14 more nutrients
  ],
  "created_at": "2026-02-07T16:19:33.678000",
  "updated_at": "2026-02-07T16:19:33.678000"
}
```

---

## AI Food Resolution System

### Overview

Natural language food parsing system using Claude AI to convert text like "I had 2 eggs and toast for breakfast" into structured food data ready for logging.

### Key Features

- **Natural Language Parsing**: Understands quantities, units, food names, and preparation methods
- **Tool Calling**: Uses Claude's tool calling for guaranteed JSON schema compliance
- **Database Matching**: Automatically matches parsed items against food database using fuzzy search
- **Confidence Scoring**: AI assigns confidence (0.0-1.0) based on input clarity
- **Meal Detection**: Automatically identifies meal context (breakfast, lunch, dinner, snack)
- **Multi-Option Matching**: Returns top 3 database matches per item for user confirmation
- **Error Handling**: Graceful handling of vague input, API failures, and rate limits

### Components

**1. Pydantic Schemas** (`whati8/schemas/food_resolver.py`)

```python
class FoodResolveRequest(BaseModel):
    """Request to resolve natural language food input."""
    text: str  # "I had 2 eggs and toast for breakfast"
    meal_hint: str | None  # Optional: "breakfast", "lunch", "dinner", "snack"
    max_matches_per_item: int = 3  # Top N database matches per item

class ParsedFoodItem(BaseModel):
    """Food item extracted by AI."""
    food_name: str  # "egg", "toast"
    quantity: float  # 2.0
    unit: str  # "pieces", "oz", "g", "cup", etc.
    original_text: str | None  # "2 eggs"
    confidence: float  # 0.0-1.0 (0.9+ = clear, <0.7 = ambiguous)

class FoodMatchOption(BaseModel):
    """Database match for a parsed item."""
    food_id: int
    name: str
    serving_size: float
    unit: str
    similarity_score: float  # 0.0-1.0 (fuzzy match score)
    # Nutrient preview
    calories: float | None
    protein: float | None
    carbs: float | None
    fat: float | None
    quantity_multiplier: float  # For unit conversion

class ResolvedFoodItem(BaseModel):
    """Parsed item + database matches."""
    parsed_item: ParsedFoodItem
    matches: list[FoodMatchOption]  # Top N matches
    status: str  # "matched", "not_found", "ambiguous"

class FoodResolveResponse(BaseModel):
    """Complete resolution result."""
    original_text: str
    resolved_items: list[ResolvedFoodItem]
    meal_context: MealContext | None  # Detected meal
    overall_confidence: float  # Average confidence
    ai_provider: str  # "anthropic"
```

**2. Service Layer** (`whati8/services/food_resolver.py`)

```python
class FoodResolverService:
    """Service for AI-powered food resolution."""

    @staticmethod
    def parse_food_text(
        text: str,
        meal_hint: str | None = None
    ) -> tuple[list[ParsedFoodItem], str | None]:
        """Parse natural language with Claude AI tool calling."""
        # Uses Claude 3.5 Sonnet with structured tool schema
        # Returns (parsed items, detected meal name)

    @staticmethod
    async def match_food_in_database(
        db: AsyncSession,
        food_name: str,
        max_results: int = 3
    ) -> list[FoodMatchOption]:
        """Fuzzy search database for matching foods."""
        # Uses pg_trgm similarity (same as /foods/search)
        # Returns top N matches with nutrients

    @staticmethod
    async def get_meal_by_name(
        db: AsyncSession,
        meal_name: str
    ) -> Meal | None:
        """Look up standard meal."""

    @staticmethod
    async def resolve_foods(
        db: AsyncSession,
        text: str,
        meal_hint: str | None = None,
        max_matches_per_item: int = 3
    ) -> FoodResolveResponse:
        """Main orchestrator: parse + match + package."""
```

**3. API Endpoint** (`whati8/api/routers/food.py`)

**POST /foods/resolve** - Resolve natural language food input
- Request body: `FoodResolveRequest`
- Returns: `FoodResolveResponse`
- Authentication required
- Error codes:
  - `400`: Input too vague or could not be parsed
  - `401`: Authentication required
  - `429`: AI service rate limit exceeded
  - `500`: AI service error or configuration issue

### System Prompt

The AI is instructed to:
- Standardize food names ("eggs" → "egg")
- Convert word quantities to numbers ("two" → 2)
- Standardize units (oz, g, kg, lb, cup, tbsp, tsp, ml, pieces, slices, serving)
- Include preparation methods if mentioned ("scrambled eggs", "grilled chicken")
- Set confidence based on clarity:
  - **0.9-1.0**: Clear quantity and food ("2 eggs", "8oz chicken")
  - **0.7-0.89**: Clear food, vague quantity ("some chicken", "a bowl of rice")
  - **0.5-0.69**: Ambiguous food or quantity ("had a snack")
  - **<0.5**: Very unclear
- Estimate reasonable quantities when not explicit (confidence <0.8)
- Detect meal context (breakfast, lunch, dinner, snack) if mentioned

### Usage Examples

**Example 1: Simple breakfast**

Request:
```json
POST /foods/resolve
{
  "text": "I had 2 eggs and toast for breakfast"
}
```

Response:
```json
{
  "original_text": "I had 2 eggs and toast for breakfast",
  "resolved_items": [
    {
      "parsed_item": {
        "food_name": "egg",
        "quantity": 2.0,
        "unit": "pieces",
        "original_text": "2 eggs",
        "confidence": 0.95
      },
      "matches": [
        {
          "food_id": 1234,
          "name": "Egg, whole, raw",
          "serving_size": 50.0,
          "unit": "g",
          "similarity_score": 0.89,
          "calories": 72.0,
          "protein": 6.3,
          "carbs": 0.4,
          "fat": 4.8,
          "quantity_multiplier": 1.0
        },
        // ... 2 more matches
      ],
      "status": "matched"
    },
    {
      "parsed_item": {
        "food_name": "toast",
        "quantity": 2.0,
        "unit": "slices",
        "original_text": "toast",
        "confidence": 0.85
      },
      "matches": [
        {
          "food_id": 5678,
          "name": "Bread, white, toasted",
          "serving_size": 25.0,
          "unit": "g",
          "similarity_score": 0.92,
          "calories": 79.0,
          "protein": 2.6,
          "carbs": 14.7,
          "fat": 1.0,
          "quantity_multiplier": 1.0
        },
        // ... 2 more matches
      ],
      "status": "matched"
    }
  ],
  "meal_context": {
    "meal_id": 1,
    "meal_name": "Breakfast"
  },
  "overall_confidence": 0.90,
  "ai_provider": "anthropic"
}
```

**Example 2: Measured dinner**

Request:
```json
{
  "text": "8oz grilled chicken breast with broccoli"
}
```

Response:
```json
{
  "original_text": "8oz grilled chicken breast with broccoli",
  "resolved_items": [
    {
      "parsed_item": {
        "food_name": "grilled chicken breast",
        "quantity": 8.0,
        "unit": "oz",
        "confidence": 0.95
      },
      "matches": [
        {"food_id": 1111, "name": "Chicken, breast, grilled", "similarity_score": 0.94, ...},
        {"food_id": 1112, "name": "Chicken breast, cooked", "similarity_score": 0.88, ...},
        {"food_id": 1113, "name": "Poultry, chicken, breast", "similarity_score": 0.82, ...}
      ],
      "status": "matched"
    },
    {
      "parsed_item": {
        "food_name": "broccoli",
        "quantity": 1.0,  // AI estimated
        "unit": "cup",
        "confidence": 0.70  // Lower due to vague quantity
      },
      "matches": [
        {"food_id": 2222, "name": "Broccoli, cooked", "similarity_score": 0.96, ...},
        // ...
      ],
      "status": "matched"
    }
  ],
  "meal_context": null,  // No meal mentioned
  "overall_confidence": 0.83,
  "ai_provider": "anthropic"
}
```

**Example 3: Ambiguous input**

Request:
```json
{
  "text": "had some chicken and rice"
}
```

Response:
```json
{
  "overall_confidence": 0.68,  // Low confidence due to vague quantities
  "resolved_items": [
    {
      "parsed_item": {
        "food_name": "chicken",
        "quantity": 3.0,  // AI estimated "some" as 3oz
        "unit": "oz",
        "confidence": 0.65
      },
      "matches": [
        {"food_id": 1234, "name": "Chicken, raw", "similarity_score": 0.45, ...},
        {"food_id": 1235, "name": "Chicken, cooked", "similarity_score": 0.44, ...},
        {"food_id": 1236, "name": "Chicken breast", "similarity_score": 0.42, ...}
      ],
      "status": "ambiguous"
    },
    // ... similar for "rice"
  ],
  "meal_context": null,
  "ai_provider": "anthropic"
}
```

### Configuration

**Environment Variables (`.env`):**
```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Optional (defaults to claude-3-5-sonnet-20241022)
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

### Cost Considerations

**Claude 3.5 Sonnet Pricing** (as of 2026):
- Input: ~$3 per million tokens
- Output: ~$15 per million tokens

**Typical Request:**
- Input: ~400 tokens (system prompt + user input)
- Output: ~150 tokens (structured JSON)
- **Cost per request: ~$0.001-0.003**

**Monthly Estimates:**
- 100 users × 3 resolutions/day = 9,000 requests/month = **$9-27/month**
- ~$0.09-0.27 per active user per month

**Optimization Strategies:**
- System prompt caching (reduces repeated input tokens)
- Rate limiting per user (e.g., 20/day)
- Future: Use Claude Haiku for simple inputs (10× cheaper)

### Error Handling

**ValueError** (400 Bad Request):
- No food items could be extracted
- Input too vague (e.g., "xyz", "food")
- Solution: Ask user for more detail

**anthropic.AuthenticationError** (500 Internal Server Error):
- Invalid or missing ANTHROPIC_API_KEY
- Solution: Check server configuration

**anthropic.RateLimitError** (429 Too Many Requests):
- AI service rate limit exceeded
- Solution: Retry after delay, implement per-user rate limiting

**anthropic.APIError** (500 Internal Server Error):
- Generic AI service error
- Solution: Log error, show user-friendly message

### Testing

**Python Test Script:**
```bash
uv run python scripts/test_food_resolver.py
```

**Bash Test Script:**
```bash
./scripts/test_food_resolver.sh
```

**Manual Testing:**
1. Start server: `uv run python -m whati8 serve --reload`
2. Login to get token: `curl -X POST http://localhost:8000/auth/login ...`
3. Test endpoint:
```bash
curl -X POST http://localhost:8000/foods/resolve \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "I had 2 eggs and toast for breakfast"}'
```
4. Or use Swagger UI: http://localhost:8000/docs

### Future Enhancements

1. **Auto-logging shortcut** - `POST /foods/resolve-and-log` (skip confirmation step)
2. **Photo upload** - Claude Vision for food identification from images
3. **User preference learning** - Personalize match ranking based on history
4. **Recipe resolution** - Detect multi-ingredient dishes ("chicken parmesan" → sauce + cheese + chicken)
5. **Batch optimization** - Cache common parses, use Claude Haiku for simple inputs
6. **Meal templates** - "Log my usual breakfast" shortcut
7. **Nutrition preview** - Show calorie/macro totals before confirmation

---

## Setup Instructions

### Prerequisites

- Python 3.10+ (3.11 or 3.12 recommended)
- PostgreSQL 14+
- uv (Python package manager)
- API Keys:
  - [USDA Food Data Central](https://fdc.nal.usda.gov/api-key-signup.html) - Free
  - [Anthropic API](https://console.anthropic.com/) - For Claude

### 1. Clone and Install

```bash
# Clone repository
git clone https://github.com/aaronpcooley/whati8.git
cd whati8

# Create virtual environment and install dependencies
uv venv
uv sync
```

### 2. Environment Configuration

Create `.env` file:

```bash
# Database
DATABASE_URL=postgresql://whati8:whati8@localhost:5432/whati8

# USDA Food Data Central API
USDA_API_KEY=YOUR_USDA_API_KEY_HERE

# AI/LLM Service
ANTHROPIC_API_KEY=YOUR_ANTHROPIC_KEY_HERE

# Authentication
JWT_SECRET=your-secret-key-change-in-production-use-openssl-rand-hex-32
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Application
DEBUG=true
LOG_LEVEL=info
```

**Generate secure JWT secret:**
```bash
openssl rand -hex 32
```

### 3. Database Setup

#### Option A: Automated (Recommended)

```bash
./scripts/setup_db.sh
```

This will:
1. Create PostgreSQL database and user
2. Enable pg_trgm extension for fuzzy search
3. Run Alembic migrations (create 9 tables)
4. Seed 18 standard nutrients
5. Seed 4 standard meals

#### Option B: Manual

```bash
# Create database and user
sudo -u postgres psql -c "CREATE USER whati8 WITH PASSWORD 'whati8';"
sudo -u postgres psql -c "CREATE DATABASE whati8 OWNER whati8;"
sudo -u postgres psql -d whati8 -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"

# Run migrations
uv run alembic upgrade head

# Seed standard data
uv run python scripts/seed_standard_data.py
```

### 4. Verify Setup

```bash
# Run verification script
uv run python scripts/verify_setup.py

# Check tables created (should show 9)
psql -U whati8 -d whati8 -c "\dt"

# Check standard nutrients (should return 18)
psql -U whati8 -d whati8 -c "SELECT COUNT(*) FROM nutrients;"

# Check standard meals (should show 4)
psql -U whati8 -d whati8 -c "SELECT * FROM meals ORDER BY display_order;"
```

### 5. Test Authentication

#### CLI Commands

```bash
# Register a user
uv run python -m whati8 auth register
# Enter: username, email, password

# Login
uv run python -m whati8 auth login
# Enter: username/email, password
# Copy the JWT token from output

# Validate token
uv run python -m whati8 auth whoami <paste-token-here>
```

#### REST API Server

```bash
# Start development server (accessible over LAN)
uv run python -m whati8 serve --reload

# Server will be available at:
# - Local: http://localhost:8000/docs
# - LAN: http://192.168.1.11:8000/docs (replace with your server IP)

# Custom host/port
uv run python -m whati8 serve --host 0.0.0.0 --port 8080 --reload
```

**Access API Documentation:**
- **Swagger UI**: http://localhost:8000/docs (interactive, test endpoints)
- **ReDoc**: http://localhost:8000/redoc (clean, readable docs)
- **OpenAPI JSON**: http://localhost:8000/openapi.json (machine-readable spec)

#### Test REST API

**Option A: Automated Test Script**
```bash
./scripts/test_api.sh
```

**Option B: Manual Testing with curl**
```bash
# 1. Register a new user
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","email":"test@example.com","password":"password123"}'

# 2. Login and get token
TOKEN=$(curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"login":"testuser","password":"password123"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# 3. Get current user (protected endpoint)
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

**Option C: Swagger UI (Recommended)**
1. Start server: `uv run python -m whati8 serve --reload`
2. Open browser: http://localhost:8000/docs
3. Click "Try it out" on any endpoint
4. For protected endpoints: Click "Authorize" button, paste token

---

## Usage Examples

### Working with Flexible Goals

```python
from whati8.models import UserGoal
from whati8.database import AsyncSessionLocal

async def set_user_goals():
    async with AsyncSessionLocal() as db:
        # User A tracks calories and protein
        goals = [
            UserGoal(user_id=1, goal_type="calories", target_value=2000, unit="kcal"),
            UserGoal(user_id=1, goal_type="protein_g", target_value=150, unit="g"),
        ]

        # User B tracks Weight Watchers points
        goals = [
            UserGoal(user_id=2, goal_type="ww_points", target_value=23, unit="points"),
        ]

        db.add_all(goals)
        await db.commit()
```

### Creating Foods with Nutrients

```python
from whati8.models import Food, FoodNutrient, Nutrient
from sqlalchemy import select

async def create_food_with_nutrients():
    async with AsyncSessionLocal() as db:
        # Get standard nutrients
        result = await db.execute(
            select(Nutrient).where(Nutrient.name.in_(["Calories", "Protein"]))
        )
        nutrient_map = {n.name: n.id for n in result.scalars()}

        # Create food
        food = Food(name="Chicken Breast", serving_size=100, unit="g")
        db.add(food)
        await db.flush()  # Get food.id

        # Add nutrients
        food.food_nutrients.extend([
            FoodNutrient(nutrient_id=nutrient_map["Calories"], amount_per_serving=165),
            FoodNutrient(nutrient_id=nutrient_map["Protein"], amount_per_serving=31),
        ])
        await db.commit()
```

### Logging Food to Meal

```python
from whati8.models import FoodLog, Meal
from datetime import datetime

async def log_food():
    async with AsyncSessionLocal() as db:
        # Get breakfast meal
        breakfast = await db.scalar(
            select(Meal).where(Meal.name == "Breakfast")
        )

        # Log food
        log = FoodLog(
            user_id=1,
            food_id=food_id,
            meal_id=breakfast.id,
            quantity=1.5,  # 1.5 servings
            logged_at=datetime.now(),
        )
        db.add(log)
        await db.commit()
```

### Fuzzy Food Search

```python
from sqlalchemy import func

async def fuzzy_search(search_term: str):
    """Typo-tolerant search: 'chiken' → 'chicken'"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Food)
            .where(func.similarity(Food.name, search_term) > 0.3)
            .order_by(func.similarity(Food.name, search_term).desc())
            .limit(20)
        )
        return result.scalars().all()
```

### Creating Custom Meals

```python
from whati8.models import Meal

async def create_custom_meal():
    async with AsyncSessionLocal() as db:
        meal = Meal(
            name="Pre-Workout",
            created_by_user_id=1,
            display_order=5,
        )
        db.add(meal)
        await db.commit()
```

---

## API Reference

### Overview

The whati8 REST API provides HTTP endpoints for all authentication and data management operations. Built with FastAPI, it features automatic OpenAPI documentation, request/response validation, and JWT-based authentication.

**Base URL**: `http://localhost:8000` (development)

**Authentication**: Bearer token in `Authorization` header for protected endpoints

### API Architecture

```
whati8/api/
├── app.py              # FastAPI factory (CORS, exception handlers, routers)
├── deps.py             # Shared dependencies (get_current_user, get_db)
├── exceptions.py       # Exception handlers (consistent error responses)
└── routers/
    ├── auth.py         # Authentication endpoints
    └── food.py         # Food search endpoints
```

**Design Pattern:**
- **Modular routers** for easy scaling (future: logs, recipes, dashboard)
- **Dependency injection** for authentication and database sessions
- **Centralized exception handling** for consistent API responses
- **Service layer reuse** - API endpoints delegate to service layer

### Endpoints

#### Health Check

**GET /health**

Health check endpoint for monitoring.

**Response (200 OK):**
```json
{
  "status": "healthy"
}
```

---

#### Authentication: Register

**POST /auth/register**

Register a new user account.

**Request Body:**
```json
{
  "username": "testuser",     // 3-50 characters, unique
  "email": "test@example.com", // Valid email, unique
  "password": "password123"    // Minimum 8 characters
}
```

**Response (201 Created):**
```json
{
  "id": 1,
  "username": "testuser",
  "email": "test@example.com",
  "created_at": "2026-02-07T19:10:50.915174"
}
```

**Errors:**
- `409 Conflict` - Username or email already exists
- `422 Unprocessable Entity` - Validation error (short password, invalid email, etc.)

**Example:**
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","email":"test@example.com","password":"password123"}'
```

---

#### Authentication: Login

**POST /auth/login**

Authenticate and receive JWT access token.

**Request Body:**
```json
{
  "login": "testuser",      // Username OR email
  "password": "password123"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400  // Seconds (24 hours default)
}
```

**Errors:**
- `401 Unauthorized` - Incorrect username/email or password
- `422 Unprocessable Entity` - Missing required fields

**Example:**
```bash
TOKEN=$(curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"login":"testuser","password":"password123"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
```

---

#### Authentication: Get Current User

**GET /auth/me** 🔒

Get current authenticated user's profile. Requires authentication.

**Request Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
  "id": 1,
  "username": "testuser",
  "email": "test@example.com",
  "created_at": "2026-02-07T19:10:50.915174"
}
```

**Errors:**
- `401 Unauthorized` - Invalid, expired, or missing token
- `404 Not Found` - User not found in database

**Example:**
```bash
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

---

#### Food Search: Search Foods

**GET /foods/search** 🔒

Search for foods using fuzzy text matching with typo-tolerance.

**Query Parameters:**
- `q` (required) - Search query, minimum 2 characters
- `limit` (optional) - Results per page, 1-100, default 20
- `offset` (optional) - Result offset for pagination, default 0

**Request Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
  "query": "chicken",
  "results": [
    {
      "id": 6318,
      "name": "Fat, chicken",
      "brand": null,
      "serving_size": 205.0,
      "unit": "g",
      "usda_fdc_id": 173564,
      "similarity": 0.67,
      "calories": 900.0,
      "protein": 0.0,
      "carbs": 0.0,
      "fat": 99.8
    }
  ],
  "total": 446,
  "limit": 5,
  "offset": 0
}
```

**Features:**
- **Typo-tolerant:** "chiken" still finds "chicken" foods
- **Similarity scoring:** 0-1 range, higher = better match
- **Key nutrients:** Calories, protein, carbs, fat included
- **Pagination:** Use offset/limit for large result sets

**Errors:**
- `401 Unauthorized` - Authentication required
- `422 Unprocessable Entity` - Query too short (< 2 chars)

**Examples:**
```bash
# Basic search
curl "http://localhost:8000/foods/search?q=chicken" \
  -H "Authorization: Bearer $TOKEN"

# Typo-tolerant search
curl "http://localhost:8000/foods/search?q=chiken&limit=5" \
  -H "Authorization: Bearer $TOKEN"

# Pagination
curl "http://localhost:8000/foods/search?q=egg&limit=20&offset=20" \
  -H "Authorization: Bearer $TOKEN"
```

---

#### Food Search: Get Food Details

**GET /foods/{food_id}** 🔒

Get detailed food information with all nutrients.

**Path Parameters:**
- `food_id` (required) - Food ID

**Request Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
  "id": 102,
  "name": "Broccoli, raw",
  "brand": null,
  "serving_size": 76.0,
  "unit": "g",
  "usda_fdc_id": 747447,
  "created_by_user_id": null,
  "notes": "USDA FDC ID: 747447",
  "food_nutrients": [
    {
      "nutrient": {
        "id": 1,
        "name": "Calories",
        "unit": "kcal",
        "description": "Energy content"
      },
      "amount_per_serving": 31.0
    },
    {
      "nutrient": {
        "id": 2,
        "name": "Protein",
        "unit": "g",
        "description": "Protein content"
      },
      "amount_per_serving": 2.57
    }
    // ... 12 more nutrients
  ],
  "created_at": "2026-02-07T16:14:33.677000",
  "updated_at": "2026-02-07T16:14:33.677000"
}
```

**Errors:**
- `401 Unauthorized` - Authentication required
- `404 Not Found` - Food ID does not exist

**Example:**
```bash
curl "http://localhost:8000/foods/102" \
  -H "Authorization: Bearer $TOKEN"
```

---

### Error Responses

All API errors return consistent JSON format:

```json
{
  "detail": "Error message",
  "status_code": 400
}
```

**Common Status Codes:**
- `200 OK` - Request succeeded
- `201 Created` - Resource created successfully
- `401 Unauthorized` - Authentication required or failed
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource already exists (duplicate)
- `422 Unprocessable Entity` - Validation error

**Validation Errors (422):**
```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "password"],
      "msg": "String should have at least 8 characters",
      "input": "short",
      "ctx": {"min_length": 8}
    }
  ]
}
```

### Security

**Authentication Flow:**
1. Client calls `POST /auth/login` with credentials
2. Server validates and returns JWT token
3. Client includes token in `Authorization: Bearer <token>` header
4. Protected endpoints validate token via `get_current_user` dependency
5. Dependency decodes JWT, verifies signature/expiration, fetches user
6. Endpoint receives authenticated `User` object

**Security Features:**
- ✅ bcrypt password hashing (12 rounds)
- ✅ JWT tokens with HMAC-SHA256 signing
- ✅ Configurable token expiration (24h default)
- ✅ HTTPBearer token extraction
- ✅ Token signature verification
- ✅ User existence validation on each request
- ✅ Generic error messages (don't leak info)
- ✅ CORS configurable for production

### Testing

**Automated Test Script:**
```bash
./scripts/test_api.sh
```

The test script validates:
- ✅ Health check
- ✅ User registration
- ✅ Login and token generation
- ✅ Protected endpoint access
- ✅ Error handling (duplicates, invalid credentials, missing token, validation)

**Manual Testing with Swagger UI:**
1. Start server: `uv run python -m whati8 serve --reload`
2. Open: http://localhost:8000/docs
3. Click "Try it out" on endpoints
4. For protected endpoints: Click "Authorize", paste token

**LAN Access:**
The server binds to `0.0.0.0` by default for LAN accessibility:
- From server: http://localhost:8000
- From LAN devices: http://192.168.1.11:8000 (replace with server IP)
- **Firewall**: May need to open port: `sudo ufw allow 8000`

### OpenAPI Documentation

**Swagger UI** (Interactive): http://localhost:8000/docs
- Try endpoints directly in browser
- See request/response schemas
- Test authentication flow
- View example values

**ReDoc** (Clean): http://localhost:8000/redoc
- Beautiful, responsive documentation
- Easy to read and navigate
- Print-friendly

**OpenAPI JSON** (Machine-readable): http://localhost:8000/openapi.json
- Full API specification
- For code generation tools
- For API clients

### Future Endpoints

The authentication API establishes the pattern for future endpoints:

**Food Management:**
- `GET /foods/search?q=chicken` - Search foods with fuzzy matching
- `GET /foods/{id}` - Get food details with nutrients
- `POST /foods` - Create custom food (authenticated)

**Food Logging:**
- `POST /logs` - Log food consumption (authenticated)
- `GET /logs?date=2026-02-07` - Get logs for date (authenticated)
- `PUT /logs/{id}` - Update log (authenticated)
- `DELETE /logs/{id}` - Delete log (authenticated)

**Dashboard:**
- `GET /dashboard/today` - Today's nutrition summary (authenticated)
- `GET /dashboard/week` - Weekly trends (authenticated)

**Goals & Meals:**
- `GET /goals` - Get user goals (authenticated)
- `POST /goals` - Create/update goal (authenticated)
- `GET /meals` - Get meals (authenticated)
- `POST /meals` - Create custom meal (authenticated)

All future endpoints will:
- Use service layer for business logic
- Require authentication with `Depends(get_current_user)`
- Use Pydantic schemas for validation
- Follow consistent error handling patterns

---

## Next Steps

### Immediate (Phase 1 Continuation)

1. **USDA Import Script** - Populate food database
   - CLI command: `uv run python -m whati8 import-usda`
   - Bulk download USDA FoodData Central JSON
   - Parse and insert into foods + food_nutrients tables
   - Initial import: ~50,000 foods with nutritional data

2. **Food Search API** - Enable food lookup
   - `GET /foods/search?q=<query>` with pg_trgm fuzzy matching
   - `GET /foods/{id}` with full nutrient details
   - Pydantic schemas: FoodResponse, FoodSearchResult
   - Authentication required

3. **Food Logging API** - Track daily consumption
   - `POST /logs` - Create food log entry
   - `GET /logs?date=2026-02-07` - Get logs for specific date
   - `PUT /logs/{id}` - Update log entry
   - `DELETE /logs/{id}` - Delete log entry
   - Pydantic schemas: FoodLogCreate, FoodLogUpdate, FoodLogResponse

4. **Daily Dashboard API** - Nutrition summaries
   - `GET /dashboard/today` - Current day nutrition totals
   - `GET /dashboard/week` - Weekly trends
   - Calculate totals for each tracked nutrient
   - Compare against user goals
   - Group by meal categories

5. **Goal & Meal Management API** - User customization
   - `GET /goals`, `POST /goals`, `PUT /goals/{id}` - Manage user goals
   - `GET /meals`, `POST /meals` - Standard + custom meals
   - Pydantic schemas: UserGoalCreate, MealCreate

### Future Phases

**Phase 2: AI & UI**
- Natural language food parsing with Claude
- Web UI for chat-based food logging
- Voice input support
- Photo recognition (OCR for recipes, image recognition for foods)

**Phase 3: Production**
- Comprehensive test coverage
- Performance optimization
- Security hardening
- Deployment to cloud (AWS/GCP)
- Alpha/Beta testing

---

## Database Commands Reference

```bash
# Connect to database
psql -U whati8 -d whati8

# List tables
\dt

# Describe table structure
\d users

# List indexes
\di

# Check extensions
SELECT * FROM pg_extension;

# Query data
SELECT * FROM users;
SELECT * FROM nutrients WHERE created_by_user_id IS NULL;
SELECT * FROM meals ORDER BY display_order;
```

## Alembic Commands Reference

```bash
# Check current migration version
uv run alembic current

# Upgrade to latest
uv run alembic upgrade head

# Downgrade one version
uv run alembic downgrade -1

# Generate new migration
uv run alembic revision --autogenerate -m "Description"

# Show migration history
uv run alembic history
```

## Development Workflow

```bash
# Install dependencies
uv sync

# Run CLI commands
uv run python -m whati8 auth register
uv run python -m whati8 auth login

# Run verification
uv run python scripts/verify_setup.py

# Run API server (when implemented)
uv run uvicorn whati8.main:app --reload

# Run tests (when implemented)
uv run pytest
```

---

## File Reference

### Configuration
- `.env` - Environment variables
- `pyproject.toml` - Dependencies and project metadata
- `alembic.ini` - Alembic configuration

### Code
- `whati8/config.py` - Settings (Pydantic)
- `whati8/database.py` - Database connection
- `whati8/models/` - SQLAlchemy models (9 files)
- `whati8/schemas/auth.py` - Auth Pydantic schemas
- `whati8/services/auth.py` - Auth business logic
- `whati8/cli/` - CLI commands

### Scripts
- `scripts/setup_db.sh` - Automated database setup
- `scripts/seed_standard_data.py` - Seed nutrients and meals
- `scripts/verify_setup.py` - Verify installation

### Migrations
- `alembic/env.py` - Alembic environment (async-configured)
- `alembic/versions/` - Migration files

---

**Status**: Phase 1 Core Implementation - Auth Complete, Ready for REST API Development
