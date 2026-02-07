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

### ⏭️ Next Steps (Phase 1 Continuation)

1. **Pydantic Schemas** - Food, FoodLog, Recipe schemas
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
├── api/                   # FastAPI application
│   ├── __init__.py        # Export app instance
│   ├── app.py             # FastAPI app factory
│   ├── deps.py            # Shared dependencies (auth, db)
│   ├── exceptions.py      # Exception handlers
│   └── routers/           # API route modules
│       ├── __init__.py
│       └── auth.py        # Auth endpoints
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
    └── auth.py         # Authentication endpoints
```

**Design Pattern:**
- **Modular routers** for easy scaling (future: foods, logs, recipes)
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
