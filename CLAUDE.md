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

### ✅ Completed (Production Ready)
- ✅ Flexible database schema (9 tables: users, nutrients, foods, food_nutrients, meals, food_logs, recipes, recipe_ingredients, user_goals)
- ✅ Async SQLAlchemy 2.0 models with full type hints
- ✅ Alembic migrations (async-enabled)
- ✅ Configuration layer (Pydantic Settings)
- ✅ Setup scripts (database creation, seeding, verification)
- ✅ **Authentication system** (Complete)
  - Async password hashing with bcrypt (non-blocking)
  - JWT token management (python-jose)
  - Strong JWT secret validation (entropy checks)
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
  - N+1 query problem fixed (2 queries instead of 21)
- ✅ **AI Food Resolution API** (Complete)
  - POST /foods/resolve - Natural language food parsing
  - Anthropic Claude integration (async, non-blocking)
  - Input sanitization (prompt injection protection)
  - Database matching with fuzzy search
  - Rate limiting (5 requests/minute)
- ✅ **Food Logging CRUD** (Complete)
  - POST /logs - Create food log entry
  - GET /logs - List with filtering (date, meal, pagination)
  - GET /logs/{id} - Get single log with details
  - PUT /logs/{id} - Update existing log
  - DELETE /logs/{id} - Delete log
  - Authorization enforcement (users can only access their own logs)
- ✅ **Conversational Agent UI** (Complete - Feb 8, 2026 Evening)
  - POST /agent/chat - Main conversational endpoint
  - Multi-turn tool calling with Claude Sonnet 4.5
  - 7 agent tools: log_food, search_foods, resolve_foods_nl, list_logs, get_daily_summary, delete_log, show_confirmation_form
  - Conversation history (60-min expiration, in-memory)
  - Natural language food logging ("I had 2 eggs for breakfast")
  - Food selection modals (auto-triggered on multiple matches)
  - Local timestamps (all chat messages display in user's local time)
  - Smart deduplication (centralized logic prefers human-readable portions like "69g/fruit" over generic "100g")
  - Permissive matching (0.05 threshold, top 20 results)
  - Svelte 4 frontend with Tailwind CSS
  - Mobile-first responsive design
  - JWT authentication with login/register modal
  - Production build deployed (single-server, static files served by FastAPI)
- ✅ **Production Readiness** (Complete)
  - Security: CORS restrictions, rate limiting, authorization framework, security headers
  - Performance: Async throughout, N+1 queries fixed, proper indexing
  - Observability: Comprehensive logging, startup health checks
  - Code Quality: Constants extracted, schema base classes, standardized errors
  - Validation: Strong input validation, API key checks, entropy validation
  - Testing: All runnable tests passing (7/7), linting clean (ruff)

### ✅ All Known Issues Resolved (Feb 8, 2026 Evening)
All major agent UI issues have been fixed:
1. ~~Food selection flow~~ - Auto-detection now triggers modal reliably
2. ~~Tool result verification~~ - System prompt enhanced with strict verification rules
3. ~~Timezone display~~ - Frontend uses local time for all chat timestamps
4. ~~Similarity threshold~~ - Lowered to 0.05, returns top 20 matches
5. ~~Duplicate entries~~ - Centralized `_deduplicate_foods()` helper applied everywhere
6. ~~List logs broken~~ - Fixed missing `func` import from SQLAlchemy

### Next Steps
1. Daily dashboard API (GET /dashboard/today, /dashboard/week)
2. Goal management API (CRUD for user goals)
3. Recipe management API (CRUD for user recipes)
4. Conversation persistence (move from in-memory to database)
5. Nutrition visualizations and charts
6. Voice input support (Web Speech API)
7. Image upload for food photos (Claude Vision API)

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
- **Routes** (`whati8/api/`) - FastAPI endpoints
- **CLI** (`whati8/cli/`) - Command-line interface
- **Frontend** (`frontend/src/`) - Svelte components and stores

### 6. Conversational Agent Architecture
The agent uses multi-turn tool calling:
1. User sends message to POST /agent/chat
2. Agent receives message + conversation history
3. Claude analyzes and calls tools (silent execution)
4. Tool results sent back to Claude
5. Claude formulates comprehensive response
6. Response sent to frontend with optional forms

**Available tools:**
- `log_food` - Create food log entry
- `search_foods` - Search food database
- `resolve_foods_nl` - Parse natural language ("2 eggs")
- `list_logs` - Get user's food logs
- `get_daily_summary` - Nutrition totals
- `show_confirmation_form` - Request user confirmation

**Food logging workflow:**
```
User: "I had a kiwi fruit for a snack"
  ↓
Agent calls: resolve_foods_nl("kiwi fruit")
  ↓
Tool returns: 3 matching kiwi options
  ↓
Agent calls: show_confirmation_form(food_selection, options)
  ↓
Frontend: Shows modal with 3 clickable options
  ↓
User: Clicks "Kiwifruit, green, raw (69g/fruit)"
  ↓
Agent calls: log_food(food_id=X, quantity=69, meal="snack")
  ↓
Agent responds: "I've logged Kiwifruit, green, raw (log ID: Y)"
```

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

### Add REST API Endpoint
1. Create `whati8/api/routers/feature.py`
2. Use existing service layer (don't duplicate logic)
3. Add router to main FastAPI app in `whati8/api/app.py`
4. Use Depends(get_db) for database sessions
5. Use Depends(get_current_user) for authentication
6. Add rate limiting for AI endpoints (@limiter.limit)

### Add Agent Tool
1. Open `whati8/services/agent_service.py`
2. Add tool definition to AGENT_TOOLS list:
```python
{
    "name": "tool_name",
    "description": "What the tool does",
    "input_schema": {
        "type": "object",
        "properties": {...},
        "required": [...]
    }
}
```
3. Add tool execution handler in `_execute_tool()` method
4. Tool should call existing services (don't duplicate logic)
5. Update system prompt if needed for new capability
6. Test with curl or frontend

### Add Frontend Component
1. Create `.svelte` file in `frontend/src/lib/components/`
2. Import and use in parent component
3. Use Tailwind CSS for styling (mobile-first)
4. Use stores for state management (don't prop drill)
5. Call API via `frontend/src/lib/api/` modules
6. Test in dev mode: `npm run dev`
7. Build for production: `npm run build`

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
- `whati8/config.py` - Pydantic Settings with validation
- `whati8/database.py` - Async database connection
- `whati8/constants.py` - Application-wide constants
- `whati8/logging_config.py` - Logging configuration
- `whati8/models/` - SQLAlchemy models (9 files)
- `whati8/schemas/` - Pydantic schemas
  - `base.py` - Base schema classes (BaseORMModel, BaseRequestModel, BaseResponseModel)
  - `auth.py` - Authentication schemas
  - `food.py` - Food search schemas
  - `food_resolver.py` - AI food resolution schemas
  - `food_log.py` - Food logging schemas
  - `agent.py` - Agent chat schemas
- `whati8/services/` - Business logic
  - `auth.py` - Authentication service (async password hashing)
  - `food_resolver.py` - AI food resolution service (async, sanitized)
  - `agent_service.py` - Conversational agent with Claude integration
- `whati8/api/` - FastAPI application
  - `app.py` - FastAPI factory with security middleware, static file mounting
  - `deps.py` - Shared dependencies (auth, db)
  - `exceptions.py` - Standardized exception handlers
  - `auth_utils.py` - Authorization utilities (ownership checks)
  - `routers/` - API endpoints (auth.py, food.py, food_log.py, agent.py)
- `whati8/cli/` - Click CLI commands (auth.py)

### Frontend Files
- `frontend/src/App.svelte` - Root component
- `frontend/src/main.ts` - Entry point
- `frontend/src/lib/components/` - UI components
  - `ChatContainer.svelte` - Main chat layout
  - `MessageList.svelte` - Conversation display
  - `MessageBubble.svelte` - Individual message rendering
  - `InputBox.svelte` - Text input with send button
  - `LoginModal.svelte` - Authentication modal (login/register)
  - `FormModal.svelte` - Dynamic forms for confirmations
- `frontend/src/lib/stores/` - Svelte stores
  - `auth.ts` - Authentication state (JWT management)
  - `chat.ts` - Conversation state
  - `forms.ts` - Modal state
- `frontend/src/lib/api/` - API clients
  - `client.ts` - HTTP client with auth headers
  - `agent.ts` - Agent API calls
- `frontend/src/lib/types/chat.ts` - TypeScript interfaces
- `frontend/dist/` - Production build (served by FastAPI)

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
- `scripts/test_food_log_api.sh` - Test food logging endpoints
- `scripts/server.sh` - Start/stop/status for server daemon
- `scripts/verify_query_efficiency.py` - Verify N+1 query fixes

### Documentation
- `README.md` - User-facing documentation with setup and feature overview
- `IMPLEMENTATION.md` - Developer implementation guide (comprehensive technical details)
- `CLAUDE.md` - This file (Claude Code AI assistant instructions)

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

# API Server (Production Mode)
./scripts/server.sh start                  # Start server daemon
./scripts/server.sh stop                   # Stop server
./scripts/server.sh status                 # Check status
tail -f /tmp/whati8_server.log             # Watch logs
grep "\[Agent\]" /tmp/whati8_server.log    # Filter agent logs

# API Server (Development Mode)
uv run python -m whati8 serve --reload     # Start with auto-reload
# Access at: http://localhost:15853/docs

# Frontend Development
cd frontend
npm install                                # Install dependencies
npm run dev                                # Dev server (http://localhost:5173)
npm run build                              # Production build to dist/

# Testing
./scripts/test_api.sh                      # Test auth endpoints
./scripts/test_food_api.sh                 # Test food search endpoints
./scripts/test_food_log_api.sh             # Test food logging endpoints

# Test Agent with curl
TOKEN=$(curl -s -X POST http://localhost:15853/auth/login \
  -H "Content-Type: application/json" \
  -d '{"login":"username","password":"password"}' \
  | jq -r '.access_token')

curl -X POST http://localhost:15853/agent/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello","session_id":"test-123"}' \
  | jq

# Development
uv add <package>                           # Add dependency
uv run python -c "from whati8.models import User" # Test imports
```

## Notes

- **bcrypt warning**: `(trapped) error reading bcrypt version` is harmless - passlib fallback works
- **JWT subject**: Must be string for spec compliance, converted to int internally
- **Alembic**: Always review auto-generated migrations before applying
- **Testing**: 7/7 runnable tests passing, 47 tests require test database
- **Linting**: All ruff checks passing, code formatted consistently
- **Production**: All 17 code review issues resolved, ready for deployment

## Important Environment Variables

```bash
# Security (Required)
JWT_SECRET=<strong-random-32+-char-string>  # Min 32 chars, 10+ unique chars
ANTHROPIC_API_KEY=sk-ant-...                # Must start with sk-ant-

# CORS (Required for production)
ALLOWED_ORIGINS=http://localhost:3000,https://app.example.com

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=10
RATE_LIMIT_AI_PER_MINUTE=5

# Database
DATABASE_URL=postgresql://whati8:password@localhost:5432/whati8
```

---

**Last Updated**: 2026-02-08 Evening (Production ready - all issues resolved)

**Latest Fixes:**
- Centralized food deduplication logic (prefers human-readable portions)
- Fixed missing `func` import for list_logs tool
- Frontend timestamps now use local time
- All ruff linting checks passing
- All runnable tests passing (7/7)
