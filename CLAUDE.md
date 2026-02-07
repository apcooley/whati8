# Claude Code Instructions

Instructions and permissions for Claude Code AI assistant working on the whati8 project.

## Project Context

**whati8** is an AI-powered food and nutrition tracker built with:
- Python 3.10+, FastAPI (async)
- PostgreSQL 14+, SQLAlchemy 2.0 (async ORM)
- Pydantic v2 for validation
- JWT authentication (python-jose, bcrypt)
- USDA Food Data Central API for food data
- Anthropic Claude for natural language food parsing

## Current Status

### Completed (Phase 1 - Substantial Progress)
- ✅ Flexible database schema (9 tables: users, nutrients, foods, food_nutrients, meals, food_logs, recipes, recipe_ingredients, user_goals)
- ✅ Async SQLAlchemy 2.0 models with full type hints
- ✅ Alembic migrations (async-enabled)
- ✅ Configuration layer (Pydantic Settings)
- ✅ Setup scripts (database creation, seeding, verification)
- ✅ **Authentication system** (Complete)
  - Password hashing (bcrypt)
  - JWT token management (python-jose)
  - CLI: register, login, whoami
  - REST API: POST /auth/register, POST /auth/login, GET /auth/me
  - HTTPBearer token authentication with dependency injection
  - OpenAPI documentation (Swagger UI + ReDoc)
- ✅ **USDA Data Import** (Complete)
  - Bulk download from USDA FoodData Central
  - 8,058 foods imported (Foundation Foods + SR Legacy)
  - 130,633 nutrient relationships
  - CLI command: `uv run python -m whati8 import-usda`
  - Automated download, parsing, and insertion
- ✅ **Food Search API** (Complete)
  - Pydantic schemas for food endpoints
  - GET /foods/search - Fuzzy text search with pg_trgm
  - GET /foods/{id} - Food details with nutrients
  - Typo-tolerant search (e.g., "chiken" → "chicken")
  - Similarity scoring and pagination
  - Authentication required

### Next Steps
1. Food logging CRUD API (POST/GET/PUT/DELETE /logs)
2. Daily dashboard API (GET /dashboard/today, /dashboard/week)
3. Goal management API (CRUD for user goals)
4. Meal management API (CRUD for custom meals)
5. Recipe management API (CRUD for user recipes)

## Agreed Permissions

### Database Operations
- ✅ **Reset database when needed** - You may drop and recreate the database for clean migrations
- ✅ **Run migrations** - You can execute `alembic upgrade head` and other migration commands
- ✅ **Seed standard data** - Run seeding scripts for nutrients and meals

### Code Changes
- ✅ **Create new files** - Models, schemas, services, routes, CLI commands
- ✅ **Modify existing code** - Fix bugs, refactor, improve implementations
- ✅ **Generate migrations** - Create Alembic migrations with `alembic revision --autogenerate`
- ✅ **Update dependencies** - Add packages via `uv add <package>`

### Testing & Verification
- ✅ **Run test scripts** - Execute Python scripts to verify implementations
- ✅ **Query database** - Use psql or asyncpg to check data
- ✅ **Test CLI commands** - Run whati8 CLI commands to verify functionality

## Development Workflow

### When Starting Work
1. Check current status in IMPLEMENTATION.md
2. Review relevant model/schema files
3. Understand existing patterns before implementing new features

### When Implementing Features
1. Follow existing architectural patterns:
   - Service layer for business logic
   - Pydantic schemas for validation
   - Async/await throughout
   - Full type hints
2. Create migrations for schema changes
3. Test implementation with CLI or scripts
4. Update IMPLEMENTATION.md with changes

### When Modifying Schema
1. Update SQLAlchemy model files
2. Generate migration: `uv run alembic revision --autogenerate -m "Description"`
3. Review generated migration carefully
4. Test migration: `uv run alembic upgrade head`
5. Verify with `psql -U whati8 -d whati8 -c "\d table_name"`

### When Adding Dependencies
1. Use `uv add <package>` (not pip)
2. Check compatibility (e.g., bcrypt 4.x for passlib)
3. Update IMPLEMENTATION.md if it's a major dependency

## Key Design Principles

### 1. Async-First
All database operations use `async/await`:
```python
async def get_user(db: AsyncSession, user_id: int) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
```

### 2. Service Layer Pattern
Business logic in services, reusable from CLI or API:
```python
# whati8/services/auth.py
class AuthService:
    @staticmethod
    async def create_user(db: AsyncSession, user_data: UserCreate) -> User:
        # Business logic here
        pass

# whati8/cli/auth.py
async def register_async(...):
    async with AsyncSessionLocal() as db:
        user = await AuthService.create_user(db, user_data)

# whati8/api/auth.py (future)
@router.post("/register")
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    return await AuthService.create_user(db, user_data)
```

### 3. Type Safety
Full type hints everywhere:
```python
from sqlalchemy.orm import Mapped, mapped_column

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
```

### 4. Flexible Schema Design
Goals, nutrients, and meals are DATA (rows), not SCHEMA (columns):
```python
# ✅ Good: Track any goal type without schema changes
UserGoal(user_id=1, goal_type="calories", target_value=2000, unit="kcal")
UserGoal(user_id=2, goal_type="ww_points", target_value=23, unit="points")

# ❌ Avoid: Hardcoded columns limit flexibility
# daily_calories_target, daily_protein_g, daily_carbs_g, ...
```

### 5. Separation of Concerns
Clean layers:
- **Models** (`whati8/models/`) - SQLAlchemy ORM
- **Schemas** (`whati8/schemas/`) - Pydantic validation
- **Services** (`whati8/services/`) - Business logic
- **Routes** (`whati8/api/`) - FastAPI endpoints (future)
- **CLI** (`whati8/cli/`) - Command-line interface

## Common Tasks

### Add a New Model
1. Create `whati8/models/new_model.py`
2. Define model with `Mapped[type]` annotations
3. Add to `whati8/models/__init__.py`
4. Generate migration: `uv run alembic revision --autogenerate -m "Add new_model"`
5. Run migration: `uv run alembic upgrade head`

### Add Pydantic Schemas
1. Create `whati8/schemas/feature.py`
2. Define request/response schemas
3. Use `EmailStr`, `Field()`, etc. for validation
4. Set `from_attributes = True` in Config for ORM compatibility

### Add a Service
1. Create `whati8/services/feature.py`
2. Use static methods for stateless functions
3. Use async functions with `AsyncSession` parameter
4. Full type hints on all functions
5. Import in CLI or API routes

### Add CLI Commands
1. Create `whati8/cli/feature.py`
2. Use Click for CLI framework
3. Wrap async functions with `asyncio.run()`
4. Register in `whati8/cli/__init__.py`

### Add REST API Endpoint (Future)
1. Create `whati8/api/feature.py`
2. Use existing service layer (don't duplicate logic)
3. Add router to main FastAPI app
4. Use Depends(get_db) for database sessions
5. Use Depends(get_current_user) for authentication

## Testing Approach

### Manual Testing (Current)
```bash
# Test CLI commands
uv run python -m whati8 auth register
uv run python -m whati8 auth login

# Test Python scripts
uv run python -c "from whati8.models import User; print('OK')"

# Query database
psql -U whati8 -d whati8 -c "SELECT * FROM users;"

# Verify setup
uv run python scripts/verify_setup.py
```

### Unit Tests (Future)
- Use pytest with pytest-asyncio
- Test service layer functions
- Mock database sessions
- Test Pydantic schema validation

## Error Handling Patterns

### Database Errors
```python
from sqlalchemy.exc import IntegrityError

try:
    await db.commit()
except IntegrityError as e:
    await db.rollback()
    if "unique constraint" in str(e).lower():
        raise ValueError("Username or email already exists")
    raise
```

### JWT Errors
```python
from jose.exceptions import JWTError

try:
    payload = AuthService.decode_token(token)
except JWTError:
    raise HTTPException(401, "Invalid or expired token")
```

### Validation Errors
Pydantic automatically handles validation, but you can catch:
```python
from pydantic import ValidationError

try:
    user_data = UserCreate(**data)
except ValidationError as e:
    # e.errors() contains detailed validation errors
    raise HTTPException(422, detail=e.errors())
```

## Database Queries

### Basic Queries
```python
# Get one
user = await db.scalar(select(User).where(User.id == user_id))

# Get one or None
result = await db.execute(select(User).where(User.username == username))
user = result.scalar_one_or_none()

# Get all
result = await db.execute(select(Food).limit(20))
foods = result.scalars().all()
```

### With Relationships
```python
from sqlalchemy.orm import selectinload

# Eager load relationships
result = await db.execute(
    select(Food)
    .options(selectinload(Food.food_nutrients).selectinload(FoodNutrient.nutrient))
    .where(Food.id == food_id)
)
food = result.scalar_one()
```

### Fuzzy Search
```python
from sqlalchemy import func

# pg_trgm similarity search
result = await db.execute(
    select(Food)
    .where(func.similarity(Food.name, search_term) > 0.3)
    .order_by(func.similarity(Food.name, search_term).desc())
)
```

## Configuration

### Environment Variables
Load from `.env` via Pydantic Settings:
```python
from whati8.config import settings

# Access settings
database_url = settings.database_url
jwt_secret = settings.jwt_secret
```

### Database Connection
```python
from whati8.database import AsyncSessionLocal

# In CLI
async with AsyncSessionLocal() as db:
    # Use db

# In FastAPI (future)
async def endpoint(db: AsyncSession = Depends(get_db)):
    # Use db
```

## Security Considerations

### Password Handling
- ✅ **Always hash** with bcrypt before storing
- ✅ **Never log** plaintext passwords
- ✅ **Use hide_input=True** in CLI prompts
- ❌ **Never return** password_hash to client

### JWT Tokens
- ✅ **Set expiration** (default 24 hours)
- ✅ **Use strong secret** (32+ characters)
- ✅ **Validate on every request** to protected endpoints
- ❌ **Don't store sensitive data** in JWT payload

### API Endpoints (Future)
- ✅ **Require authentication** for all user data endpoints
- ✅ **Validate user ownership** before returning/modifying data
- ✅ **Use HTTPS** in production
- ❌ **Don't expose internal IDs** unnecessarily

## Git Workflow

### Committing Changes
When I make changes, I should create commits with:
- Clear, descriptive commit messages
- Logical grouping of changes
- Co-authored by: `Claude Sonnet 4.5 <noreply@anthropic.com>`

Example:
```bash
git add whati8/services/auth.py whati8/schemas/auth.py whati8/cli/auth.py
git commit -m "Implement authentication system with CLI

- Add password hashing with bcrypt
- Add JWT token management with python-jose
- Add CLI commands: register, login, whoami
- Add service layer for reuse in future REST API

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

## File Locations

### Core Files
- `whati8/config.py` - Pydantic Settings
- `whati8/database.py` - Async database connection
- `whati8/models/` - SQLAlchemy models (9 files)
- `whati8/schemas/` - Pydantic schemas (auth.py, food.py)
- `whati8/services/` - Business logic (auth.py)
- `whati8/api/` - FastAPI application
  - `app.py` - FastAPI factory
  - `deps.py` - Shared dependencies (auth, db)
  - `exceptions.py` - Exception handlers
  - `routers/` - API endpoints (auth.py, food.py)
- `whati8/cli/` - Click CLI commands (auth.py)

### Configuration
- `.env` - Environment variables (not in git)
- `.env.example` - Template for .env
- `pyproject.toml` - Project dependencies
- `alembic.ini` - Alembic configuration

### Scripts
- `scripts/setup_db.sh` - Database setup automation
- `scripts/seed_standard_data.py` - Seed nutrients and meals
- `scripts/verify_setup.py` - Verify installation
- `scripts/import_usda_data.py` - USDA bulk data import
- `scripts/test_api.sh` - Test authentication endpoints
- `scripts/test_food_api.sh` - Test food search endpoints

### Documentation
- `README.md` - User-facing documentation
- `IMPLEMENTATION.md` - Developer implementation guide
- `CLAUDE.md` - This file

## Quick Reference Commands

```bash
# Setup
uv sync                                    # Install dependencies
./scripts/setup_db.sh                      # Setup database
uv run python scripts/verify_setup.py      # Verify setup

# Database
psql -U whati8 -d whati8 -c "\dt"          # List tables
uv run alembic current                     # Check migration version
uv run alembic upgrade head                # Run migrations

# CLI
uv run python -m whati8 auth register      # Register user
uv run python -m whati8 auth login         # Login
uv run python -m whati8 auth whoami <token> # Validate token
uv run python -m whati8 import-usda        # Import USDA food data
uv run python -m whati8 import-usda --limit 100 # Test import

# API Server
uv run python -m whati8 serve --reload     # Start development server
# Access at: http://localhost:8000/docs

# Testing
./scripts/test_api.sh                      # Test auth endpoints
./scripts/test_food_api.sh                 # Test food search endpoints

# Development
uv add <package>                           # Add dependency
uv run python -c "from whati8.models import User" # Test imports
```

## Notes

- **bcrypt warning**: `(trapped) error reading bcrypt version` is harmless - passlib fallback works
- **JWT subject**: Must be string for spec compliance, converted to int internally
- **Alembic**: Always review auto-generated migrations before applying
- **Testing**: Use CLI for now, pytest later for unit/integration tests

---

**Last Updated**: 2026-02-07 (After USDA import and Food Search API implementation)
