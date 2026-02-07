# whati8 Implementation Guide

Complete developer guide for the whati8 nutrition tracker implementation.

## Table of Contents
- [Current Status](#current-status)
- [Architecture Overview](#architecture-overview)
- [Schema Design](#schema-design)
- [Authentication System](#authentication-system)
- [Setup Instructions](#setup-instructions)
- [Usage Examples](#usage-examples)
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

### ⏭️ Next Steps (Phase 1 Continuation)

1. **Convert Auth to REST API** - FastAPI endpoints using existing service layer
2. **Pydantic Schemas** - Food, FoodLog, Recipe schemas
3. **USDA Import** - Bulk import script to populate food_nutrients
4. **Food Search API** - Fuzzy search endpoint with authentication
5. **Logging API** - CRUD endpoints for food logs
6. **Dashboard API** - Daily nutrition summary
7. **Goal/Meal Management** - CRUD endpoints for custom goals and meals

---

## Architecture Overview

### Technology Stack

| Component | Technology | Notes |
|:----------|:-----------|:------|
| **Backend** | Python 3.10+, FastAPI | High-performance async API |
| **Database** | PostgreSQL 14+, SQLAlchemy 2.0 | Async ORM with full type safety |
| **Driver** | asyncpg | High-performance PostgreSQL driver |
| **Migrations** | Alembic | Async-enabled schema versioning |
| **Validation** | Pydantic v2 | Request/response schemas |
| **Auth** | JWT (python-jose), bcrypt (passlib) | Secure token-based auth |
| **AI/LLM** | Anthropic Claude (default) | Natural language food parsing |
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
│   └── auth.py            # Auth schemas (UserCreate, Token, etc.)
├── services/              # Business logic layer
│   └── auth.py            # Authentication service
├── api/                   # FastAPI routes (future)
└── cli/                   # CLI commands
    ├── __init__.py
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

Complete authentication system with CLI commands and service layer, ready for REST API conversion.

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

### Converting to REST API

The service layer is ready for REST API. Just create thin FastAPI route wrappers:

```python
# whati8/api/auth.py (future)
from fastapi import APIRouter, Depends, HTTPException
from whati8.services.auth import AuthService
from whati8.schemas.auth import UserCreate, UserLogin, Token, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user."""
    user = await AuthService.create_user(db, user_data)
    return user

@router.post("/login", response_model=Token)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    """Login and get JWT token."""
    user = await AuthService.authenticate_user(db, credentials.login, credentials.password)
    if not user:
        raise HTTPException(401, "Invalid credentials")

    token = AuthService.create_access_token(user.id)
    expires_in = settings.jwt_expiration_hours * 3600  # Convert to seconds
    return Token(access_token=token, expires_in=expires_in)

@router.get("/me", response_model=UserResponse)
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Get current authenticated user."""
    payload = AuthService.decode_token(token)
    user = await AuthService.get_user_by_id(db, payload.sub)
    if not user:
        raise HTTPException(401, "User not found")
    return user
```

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

## Next Steps

### Immediate (Phase 1 Continuation)

1. **REST API Endpoints** - Convert CLI to FastAPI routes
   - `POST /auth/register`, `POST /auth/login`, `GET /auth/me`
   - `GET /foods/search?q=<query>` with fuzzy matching
   - `POST /logs`, `GET /logs`, `PUT /logs/{id}`, `DELETE /logs/{id}`

2. **USDA Import Script** - Populate database
   - CLI command: `python -m whati8.cli import-usda`
   - Bulk download USDA FoodData Central JSON
   - Parse and insert into foods + food_nutrients tables

3. **Additional Pydantic Schemas**
   - Food request/response schemas
   - FoodLog schemas
   - Recipe schemas
   - Goal and Meal management schemas

4. **Daily Dashboard API**
   - `GET /dashboard/today` - Nutrition summary for current day
   - Calculate totals for each tracked nutrient
   - Compare against user goals
   - Group by meal categories

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
