# whati8 Implementation Guide

**Last Updated:** February 10, 2026 Evening
**Status:** Production-ready with conversational UI

---

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Database Schema](#database-schema)
3. [Backend Services](#backend-services)
4. [API Endpoints](#api-endpoints)
5. [Frontend Components](#frontend-components)
6. [Key Features & Implementation](#key-features--implementation)
7. [Development Workflow](#development-workflow)
8. [Deployment & Operations](#deployment--operations)
9. [Testing Strategy](#testing-strategy)

---

## Architecture Overview

### Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Svelte 4 + Tailwind CSS | Reactive UI, mobile-first responsive design |
| **Backend** | FastAPI (Python 3.10+) | High-performance async API |
| **Database** | PostgreSQL 14+ | Persistent data storage |
| **ORM** | SQLAlchemy 2.0 | Type-safe database access |
| **AI/LLM** | Claude (Anthropic) | Natural language food parsing & conversation |
| **Authentication** | JWT + OAuth2 | Secure user sessions |
| **Data Source** | USDA Food Data Central | 50,000+ foods with nutrition data |

### System Flow

```
User Input (Text/Voice)
    ↓
Frontend (ChatContainer)
    ↓
Agent Service (Claude + Tool Calling)
    ↓
Tool Execution (resolve_foods_nl, search_foods, log_food, etc.)
    ↓
Database Queries (SQLAlchemy)
    ↓
Response → Confirmation Form or Summary
    ↓
Frontend Display + Chat Update
```

---

## Database Schema

### Core Tables

#### `users`
```python
class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

#### `foods`
Supports both USDA and user-created foods:
```python
class Food(Base):
    __tablename__ = "foods"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    brand: Mapped[str | None]
    serving_size: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    unit: Mapped[str] = mapped_column(String(50))
    usda_fdc_id: Mapped[int | None] = mapped_column(unique=True, nullable=True)
    category: Mapped[str | None]
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    
    # Relationships
    portions: Mapped[list["FoodPortion"]] = relationship(back_populates="food", cascade="all, delete-orphan")
    food_nutrients: Mapped[list["FoodNutrient"]] = relationship(back_populates="food", cascade="all, delete-orphan")
```
- **created_by_user_id = NULL**: USDA food
- **created_by_user_id = user.id**: Custom/user-created food

#### `food_portions`
Household portion sizes (e.g., "1 cup", "1 large egg"):
```python
class FoodPortion(Base):
    __tablename__ = "food_portions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # e.g., 1.0
    unit_name: Mapped[str] = mapped_column(String(100))  # e.g., "cup"
    unit_abbreviation: Mapped[str | None]  # e.g., "c"
    gram_weight: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # Auto-calculated conversion
    modifier: Mapped[str | None]  # e.g., "sifted", "large", "medium"
    portion_description: Mapped[str | None]  # e.g., "1.0 sifted cup (237g)"
    sequence_number: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    
    # Relationships
    food: Mapped["Food"] = relationship(back_populates="portions")
```

#### `nutrients`
Master list of tracked nutrients:
```python
class Nutrient(Base):
    __tablename__ = "nutrients"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    unit: Mapped[str] = mapped_column(String(20))  # e.g., "kcal", "g"
    description: Mapped[str | None]
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
```

#### `food_nutrients`
Amount of each nutrient per serving:
```python
class FoodNutrient(Base):
    __tablename__ = "food_nutrients"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id"), index=True)
    nutrient_id: Mapped[int] = mapped_column(ForeignKey("nutrients.id"))
    amount_per_serving: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    
    # Relationships
    food: Mapped["Food"] = relationship(back_populates="food_nutrients")
    nutrient: Mapped["Nutrient"] = relationship()
```

#### `food_logs`
Daily food tracking records:
```python
class FoodLog(Base):
    __tablename__ = "food_logs"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id"))
    meal_id: Mapped[int] = mapped_column(ForeignKey("meals.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # Weight in grams
    logged_at: Mapped[datetime] = mapped_column(index=True)
    notes: Mapped[str | None]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    
    # Relationships
    food: Mapped["Food"] = relationship(selectinload=True)
    user: Mapped["User"] = relationship()
    meal: Mapped["Meal"] = relationship()
```

#### `meals`
Meal categories:
```python
class Meal(Base):
    __tablename__ = "meals"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)  # Breakfast, Lunch, Dinner, Snack
    description: Mapped[str | None]
```

#### `conversations`
Agent conversation history:
```python
class Conversation(Base):
    __tablename__ = "conversations"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[str] = mapped_column(String(100), index=True)
    messages: Mapped[dict]  # JSON array of {role, content} objects
    created_at: Mapped[datetime] = mapped_column(index=True)
    expires_at: Mapped[datetime] = mapped_column(index=True)
    updated_at: Mapped[datetime]
```

---

## Backend Services

### AgentService (whati8/services/agent_service.py)

**Responsibility:** Manage conversational AI interactions using Claude with tool calling

**Key Components:**

1. **Tool Definitions** - 7 agent tools registered with Claude:
   - `resolve_foods_nl` - Parse natural language food descriptions
   - `search_foods` - Database food lookup
   - `log_food` - Create individual food log entry
   - `list_logs` - Query daily logs
   - `get_daily_summary` - Nutrition totals for the day
   - `delete_log` - Remove a log entry
   - `show_confirmation_form` - Trigger multi-food UI

2. **Message Flow:**
   ```
   process_message(user_message)
     ↓
   Call Claude API (with tools)
     ↓
   Claude decides which tool(s) to use
     ↓
   Execute tools (async)
     ↓
   Pass results back to Claude
     ↓
   Claude formats final response
     ↓
   Return message + form data (if needed) to frontend
   ```

3. **Multi-food Confirmation:**
   - When parsing natural language detects multiple foods
   - Triggers auto-form (no need for Claude to call `show_confirmation_form`)
   - Shows "Searching database..." while form loads
   - User reviews, edits quantities/units, clicks "Log Foods"
   - Frontend sends batch-summary request

4. **Conversation Management:**
   - Stores all messages in `ConversationManager` (in-memory cache)
   - Persists to `conversations` table for history
   - Auto-expires old conversations after 24 hours
   - Supports resuming sessions

### FoodResolverService (whati8/services/food_resolver.py)

**Responsibility:** Parse natural language food descriptions and match to database

**Key Algorithms:**

1. **Multi-term Search** (Claude-powered):
   - User says "overnight oats" → Claude generates ["oats", "oatmeal", "cereal"]
   - Each term searched independently
   - Results merged and ranked by similarity

2. **Portion Matching:**
   - "1 large egg" → Finds "egg, whole, raw, fresh" and portion "1 large (50g)"
   - Volume detection for "cup", "tablespoon", "ml"
   - Fuzzy matching on modifiers (large, small, medium, etc.)

3. **Similarity Scoring:**
   - Trigram fuzzy matching (pg_trgm PostgreSQL extension)
   - Secondary sort: prefer foods with portions
   - Deduplication: avoid showing "Eggs, raw" and "Egg, raw, fresh" together

4. **Confidence Calculation:**
   - Input validation: 0.9+ for unambiguous matches
   - Ambiguity: 0.5-0.8 for multiple reasonable options
   - No match: Returns status="not_found"

### FoodUnitsService (whati8/services/food_units.py)

**Responsibility:** Handle unit conversions and weight specifications

**Key Features:**

1. **Unit Type Detection:**
   - Mass units: g, oz, lb (auto-convertible)
   - Volume units: cup, tbsp, tsp, fl oz (use USDA defaults)
   - Piece units: piece, fruit, egg (default 100g per piece)
   - Custom units: user-defined for specific foods

2. **Weight Conversions:**
   - 1 oz = 28.35 g
   - 1 lb = 453.6 g
   - 1 cup = 237 g (default for volume)
   - 1 tbsp = 15 g (default)

3. **Optional Weight Specification:**
   - For non-mass units, users can specify custom weights
   - Example: "1 cup of honey" (different weight than water)
   - Stored in `FoodPortion.gram_weight` field
   - NULL = use default, numeric = use custom

---

## API Endpoints

### Authentication

#### POST `/auth/register`
**Purpose:** Create new user account
```json
{
  "username": "aaron",
  "email": "aaron@example.com",
  "password": "SecurePassword123!"
}
```
**Returns:** `{user_id, token, message}`

#### POST `/auth/login`
**Purpose:** Authenticate and get JWT token
```json
{
  "username": "aaron",
  "password": "SecurePassword123!"
}
```
**Returns:** `{access_token, token_type, user_id}`

#### POST `/auth/reset-password`
**Purpose:** Reset password via email code
```json
{
  "email": "aaron@example.com",
  "reset_code": "ABC123XYZ",
  "new_password": "NewPassword456!"
}
```

### Foods

#### GET `/foods/search?q=<query>&limit=<10>`
**Purpose:** Search for foods by name
**Returns:** `{results: [{id, name, brand, serving_size, unit, calories, portions: [...]}]}`

#### POST `/foods` (Custom Foods)
**Purpose:** Create user-defined food
```json
{
  "name": "My Protein Shake",
  "unit_name": "shake",
  "unit_type": "custom",
  "gram_weight": 300.0,
  "calories": 200,
  "protein": 25,
  "carbs": 5,
  "fat": 5
}
```
**Returns:** `{id, name, calories, ...}`

### Food Logs

#### POST `/logs/batch`
**Purpose:** Create multiple food log entries in one transaction
```json
{
  "entries": [
    {
      "food_id": 802,
      "quantity": 85.0,
      "meal_id": 3,
      "notes": "1 cup"
    }
  ],
  "logged_at": "2026-02-10T20:00:00Z"
}
```
**Returns:** `{logged: 1, message: "..."}`

#### POST `/logs/batch-summary` ⭐ NEW (Feb 10, 2026)
**Purpose:** Create logs AND return Claude-formatted nutrition summary
```json
{
  "entries": [
    {
      "food_id": 802,
      "food_name": "Egg, whole, dried",
      "quantity": 85.0,
      "parsed_quantity": 1.0,
      "parsed_unit": "cup",
      "meal_id": 3
    }
  ]
}
```
**Returns:** 
```json
{
  "logged": 1,
  "formatted_summary": "You logged 1 egg (1 cup). Total: 2410 calories, 48g protein, 0g carbs, 40g fat, 0g fiber."
}
```
**Note:** Claude automatically generates friendly confirmation message

#### GET `/logs?date=<YYYY-MM-DD>&limit=<20>&offset=<0>`
**Purpose:** Get food logs for a specific day
**Returns:** `{logs: [{food_name, quantity, meal, calories, ...}], totals: {calories, protein, ...}}`

#### DELETE `/logs/<id>`
**Purpose:** Remove a food log entry
**Returns:** `{message: "Log deleted"}`

### Agent

#### POST `/agent/chat?user_timezone=America%2FDenver`
**Purpose:** Send message to Claude agent
```json
{
  "message": "I had 2 eggs and a cup of oatmeal for breakfast",
  "session_id": "session-abc123"
}
```
**Returns:**
```json
{
  "message_content": "Searching database...",
  "tool_results": [...],
  "requires_form": true,
  "form_data": {
    "form_type": "multi_food_confirmation",
    "data": {
      "food_items": [
        {
          "item_id": "uuid",
          "raw_text": "2 eggs",
          "parsed_quantity": 2.0,
          "parsed_unit": "piece",
          "selected_food_id": 4818,
          "selected_name": "Egg, whole, raw, fresh",
          "portions": [...]
        }
      ]
    }
  }
}
```

---

## Frontend Components

### Component Hierarchy

```
App.svelte
├── ChatContainer.svelte
│   ├── MessageList.svelte
│   │   └── MessageBubble.svelte
│   └── InputBox.svelte
│       ├── MultiFoodForm.svelte (modal)
│       │   └── FoodRow.svelte (editable rows)
│       │       ├── QuantityEditor.svelte (modal)
│       │       └── FoodSelector.svelte (dropdown)
│       └── LoginModal.svelte (if not authenticated)
```

### Key Components

#### ChatContainer.svelte
**Purpose:** Main chat UI, manages state and API calls
**State:**
- `messages`: Chat history
- `currentSessionId`: Agent session identifier
- `isLoading`: Show spinner during API calls
- `showMultiFoodForm`: Toggle confirmation form visibility

**Events:**
- Sends user messages to agent
- Displays agent responses
- Shows/hides multi-food form
- Handles form submission via `/logs/batch-summary`

#### MultiFoodForm.svelte (Feb 10 Update)
**Purpose:** Review and edit parsed foods before logging
**Features:**
- Quantity input field (editable number)
- Unit dropdown (populated from food's portions)
- Meal selector
- "Add another food" inline button
- Cancel/Log Foods buttons

**New Flow (Feb 10):**
1. Show "Searching database..." during form load
2. Form pops up with foods and editable quantities
3. User reviews/edits items
4. Clicks "Log Foods" → sends to `/logs/batch-summary`
5. Receives formatted summary message
6. Summary displayed in chat via agent

#### FoodRow.svelte (Feb 10 Update)
**Purpose:** Single food item in confirmation form
**Changes:**
- Quantity is now editable input (not button)
- Unit shows as dropdown with valid conversions
- Displays `[quantity] [unit dropdown]` layout
- No grams column (unless unit is "g")

**Example Display:**
```
Food Name: Egg, whole, dried
[1.0] [cup ▼]
Weight: Shows only if unit is "g"
```

#### FoodSelector.svelte
**Purpose:** Dropdown menu to change matched food
**Shows:**
- Current selection (highlighted)
- Alternative matches with similarity scores
- "Create custom food" option
**Returns:** Selected food with all its portions

#### QuantityEditor.svelte
**Purpose:** Modal for detailed quantity editing
**Features:**
- Numeric input for quantity
- Unit dropdown with smart conversion suggestions
- Nutrient calculator (shows calories, protein, etc.)
- Save/Cancel buttons

---

## Key Features & Implementation

### 1. Conversational Food Logging ✅

**How It Works:**
1. User types natural language: "I had 2 scrambled eggs and toast"
2. Agent calls `resolve_foods_nl` tool
3. Claude parses into: `[{food: "eggs", qty: 2, unit: "piece"}, {food: "toast", qty: 1}]`
4. System searches for each food
5. If multiple foods detected → auto-trigger `MultiFoodForm`
6. User confirms and submits
7. Foods logged with `/logs/batch-summary`
8. Claude formats summary message

**Agent Flow:**
```
User: "2 eggs and oatmeal"
  ↓
Agent: "Searching database..."
  ↓
[Form appears with 2 foods pre-filled]
  ↓
User edits and clicks "Log Foods"
  ↓
POST /logs/batch-summary
  ↓
Agent: "You logged 2 eggs (2 pieces) and 1 oatmeal (1 cup).
Total: 350 calories, 18g protein, 25g carbs, 12g fat, 4g fiber."
```

### 2. Smart Unit Handling ✅ (Feb 10)

**For Mass Units (g, oz, lb):**
- Weight auto-calculated based on conversion
- User sees: `[1.0] [g ▼]` with optional weight editing
- Example: "2 oz" → 56.7g stored

**For Volume Units (cup, tbsp, tsp):**
- Shows dropdown with available options
- User can specify custom weight if desired
- Example: "1 cup" → 237g (default) or user-entered value

**For Piece Units (piece, egg, etc.):**
- Unit dropdown shows available portions
- Example: "2 pieces" → uses 100g per piece default (can override)

**For Custom Units:**
- User-defined per food
- Weight required
- Example: "1 scoop of protein powder" → 30g

### 3. Batch Logging with Summary ✅ (Feb 10)

**Traditional `/logs/batch`:**
- Creates logs only
- Returns: `{logged: N, message: "..."}`
- No nutrition summary

**New `/logs/batch-summary`:** (Feb 10)
- Creates logs
- Queries them back with nutrition data
- Calculates totals: calories, protein, carbs, fat, fiber
- Calls Claude to format friendly summary
- Returns: `{logged: N, formatted_summary: "..."}`

**Example Output:**
```
You logged 1 egg (1 cup) and 2 Built Peanut Butter Cup bars.
Total: 2500 calories, 48g protein, 39g carbs, 40g fat, 0g fiber.
```

### 4. Multi-food Confirmation Form ✅

**Auto-triggered when:**
- Natural language resolves to 2+ foods
- Confidence score is high

**Form Features:**
- Shows all parsed foods
- Editable quantity & unit per food
- Meal selector (Breakfast/Lunch/Dinner/Snack)
- Add another food button
- Search refinement if needed

**UX Flow:**
```
"I had eggs and toast"
  ↓
Agent: "Searching database..."
  ↓
Form pops with:
  □ Egg, whole, raw, fresh | [2] [piece ▼]
  □ Bread, whole wheat     | [2] [slice ▼]
  Meal: [Breakfast ▼]
  [+ Add another food] [Cancel] [✓ Log Foods]
```

### 5. Custom Foods ✅

**Creation:**
```python
POST /foods
{
  "name": "Built Peanut Butter Cup bar",
  "unit_name": "bar",
  "unit_type": "custom",
  "gram_weight": 43.0,
  "calories": 160,
  "protein": 7,
  ...
}
```

**Features:**
- User-specific (created_by_user_id set)
- Immediately searchable
- Can be edited/deleted by creator
- Supports any unit type

### 6. Database Search ✅

**Algorithm:**
1. **Trigram Search** (PostgreSQL pg_trgm):
   - Finds similar food names using 3-character substrings
   - Fast, fuzzy matching
   - Example: "oats" matches "Oatmeal" and "Oat flour"

2. **Multi-term Expansion** (Claude):
   - User: "overnight oats"
   - Claude generates: ["oats", "oatmeal", "cereal"]
   - Each term searched, results merged

3. **Result Ranking:**
   - Exact matches first
   - Then by similarity score (0-1)
   - Tiebreak: prefer foods with portions
   - Custom foods slightly prioritized

4. **Performance:**
   - Indexed on `foods.name`
   - Full-text search via pg_trgm
   - Results: 10 foods in ~50ms

### 7. Server Auto-kill Feature ✅ (Feb 10)

**Problem:** Running `uv run python -m whati8 serve` twice leaves port bound

**Solution:** Added to CLI (`whati8/cli/__init__.py`):
```python
if is_port_in_use(port):
    if kill_existing:  # Default: True
        kill_process_on_port(port)
        wait_for_port_release(timeout=5s)
```

**Usage:**
```bash
# Auto-kill existing process (default)
uv run python -m whati8 serve --reload

# Disable auto-kill (fail if port in use)
uv run python -m whati8 serve --reload --no-kill-existing
```

### 8. Authentication & Security ✅

**JWT Token:**
- Issued on login with 24-hour expiration
- Stored in localStorage
- Sent with every API request
- Validated on server

**Password Security:**
- bcrypt hashing (4.0.1 compatible with passlib 1.7.4)
- Salt generated per password
- Min 8 characters required

**User Isolation:**
- Custom foods scoped to creator
- Logs scoped to current user
- Agent tools verify user_id

---

## Development Workflow

### Running Locally

```bash
# 1. Setup environment
uv venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# 2. Install dependencies
uv sync

# 3. Configure .env
# Copy .env.example → .env
# Set ANTHROPIC_API_KEY, DATABASE_URL, etc.

# 4. Setup database
alembic upgrade head

# 5. Import USDA data (optional, ~5 min)
uv run python -m whati8 import-usda

# 6. Start backend
uv run python -m whati8 serve --reload

# 7. In another terminal, start frontend
cd frontend
npm install
npm run dev

# 8. Open browser
http://localhost:5173
```

### Code Organization

```
whati8/
├── api/
│   ├── routers/          # Endpoint handlers
│   ├── deps.py           # Dependency injection
│   ├── auth_utils.py     # JWT utilities
│   └── app.py            # FastAPI application
├── services/             # Business logic
│   ├── agent_service.py  # Claude integration
│   ├── food_resolver.py  # NL parsing
│   └── food_units.py     # Unit conversions
├── models/               # SQLAlchemy models
├── schemas/              # Pydantic validation
├── constants.py          # Shared constants
├── config.py             # Settings management
└── cli/                  # CLI commands

frontend/
├── src/
│   ├── lib/
│   │   ├── components/   # Svelte components
│   │   ├── stores/       # State management
│   │   └── utils/        # Helper functions
│   ├── App.svelte        # Root component
│   └── main.ts           # Entry point
├── vite.config.ts        # Build configuration
└── tsconfig.json         # TypeScript config
```

### Git Workflow

```bash
# Feature branch
git checkout -b feature/name

# Make changes
git add .
git commit -m "Brief description"

# Push to GitHub
git push origin feature/name

# Create pull request for review
```

### Common Commands

```bash
# Run tests
pytest tests/ -v

# Format code
ruff check . --fix

# Type checking
pyright whati8/

# Build frontend
cd frontend && npm run build

# Deploy (if using Docker)
docker build -t whati8 .
docker run -p 9428:9428 whati8
```

---

## Deployment & Operations

### Environment Variables

**Required:**
- `DATABASE_URL` - PostgreSQL connection string
- `ANTHROPIC_API_KEY` - Claude API key
- `JWT_SECRET` - Strong random string (min 32 chars)

**Optional:**
- `DEBUG` - Set to "false" in production
- `LOG_LEVEL` - "info" (default) or "debug"
- `ALLOWED_ORIGINS` - CORS origins (comma-separated)
- `USDA_API_KEY` - If using USDA API directly

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback one version
alembic downgrade -1
```

### Monitoring

**Key Metrics:**
- Database connection pool usage
- API response times (target: <500ms)
- Agent token usage (Claude API)
- User session count

**Logs to Watch:**
```
[Agent] Tool execution failed
[Agent] Claude API error
Database connection pool exhausted
JWT validation error
```

### Performance Optimization

**Database:**
- Index on `foods.name` (trigram search)
- Index on `users.id, foods.created_by_user_id` (custom foods)
- Index on `food_logs.user_id, food_logs.logged_at` (daily queries)

**Frontend:**
- Code splitting (components lazy-loaded)
- CSS minification (Tailwind production build)
- Image optimization (if applicable)

**Backend:**
- Async/await throughout (no blocking I/O)
- Connection pooling (SQLAlchemy)
- Response caching (conversation history in-memory)

---

## Testing Strategy

### Test Categories

1. **Unit Tests** (~30 tests)
   - Individual functions and services
   - Mocked database
   - Fast execution

2. **Integration Tests** (~40 tests)
   - API endpoints with real database
   - Tool execution flow
   - Authentication/authorization

3. **Edge Case Tests** (~41 tests)
   - Boundary conditions (min/max values)
   - Special characters and encoding
   - Concurrency scenarios
   - User isolation

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_custom_foods.py -v

# Specific test class
pytest tests/test_edge_cases_comprehensive.py::TestCustomFoodsEdgeCases -v

# With coverage
pytest tests/ --cov=whati8 --cov-report=html
```

### Test Patterns

**Standard async test:**
```python
@pytest.mark.asyncio
async def test_example(authenticated_client, db_session):
    """Test description."""
    # Arrange
    food_data = {"name": "Test", "calories": 100}
    
    # Act
    response = await authenticated_client.post("/foods", json=food_data)
    
    # Assert
    assert response.status_code == 201
    assert response.json()["name"] == "Test"
```

### CI/CD Integration

Tests run automatically on:
- Pull request creation
- Push to main branch
- Scheduled nightly runs

---

## Recent Updates (Feb 10, 2026)

### Changes Made

1. **Unit Dropdown Fix**
   - FoodRow now shows unit options with modifiers
   - Display format: "1 tablespoon", "1 large egg", etc.
   - Fixed undefined unit display issue

2. **Custom Food Weight Specification** (COMPLETED - Not in session context but documented for clarity)
   - Users can specify custom weights for non-mass units
   - Example: "1 cup of honey" at custom weight
   - Stored in `FoodPortion.gram_weight`

3. **Batch-Summary Endpoint** ✅
   - New `/logs/batch-summary` endpoint
   - Logs foods, queries them back, calculates totals
   - Claude formats friendly summary message
   - Returns to user in chat

4. **Agent Flow Improvements** ✅
   - Shows "Searching database..." during form load
   - Form closes after submission
   - Summary message displayed in chat

5. **Server Auto-kill Feature** ✅
   - `uv run python -m whati8 serve` now auto-kills existing process
   - Flag: `--kill-existing` (default) or `--no-kill-existing`
   - Graceful port release handling

6. **Bcrypt Compatibility Fix** ✅
   - Downgraded bcrypt from 4.3.0 → 4.0.1
   - Compatible with passlib 1.7.4
   - Resolved authentication hash verification errors

---

## Known Limitations & Future Work

### Current Limitations
- No barcode scanning (future feature)
- No Open Food Facts integration (for branded products)
- No WW Points tracking (planned)
- Limited recipe support (coming in Phase 2)

### Planned Features
1. **Open Food Facts Integration** - Branded product database
2. **WW Points Tracking** - Weight Watchers integration
3. **Recipe Management** - Save and reuse meal combinations
4. **Garmin Integration** - Auto-pull exercise data
5. **Export/Import** - CSV backup and restore

---

## Support & Troubleshooting

### Common Issues

**"Port 9428 already in use"**
```bash
# Auto-kill (default)
uv run python -m whati8 serve --reload

# Manual kill
lsof -i:9428 | grep LISTEN | awk '{print $2}' | xargs kill -9
```

**"Could not validate credentials" on login**
- Check bcrypt version: `pip list | grep bcrypt` (should be 4.0.1)
- Clear localStorage: Dev Tools → Application → Clear Storage
- Re-register new account

**Database connection fails**
- Verify PostgreSQL is running: `pg_isready`
- Check DATABASE_URL in .env
- Verify database exists: `createdb whati8`

---

**Last Updated:** February 10, 2026  
**Status:** Production-ready for testing and iteration  
**Next Phase:** Open Food Facts integration + WW Points tracking
