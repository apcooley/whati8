# Architecture

## System Overview

whati8 is an AI-powered food and nutrition tracker. Users type natural language ("I had 2 eggs and toast for breakfast"), and the system parses, resolves against a food database, presents a confirmation UI, logs nutrition, and summarizes totals.

```
┌──────────────────────────────────────────────────────────────────┐
│                        Frontend (Svelte 4)                       │
│  ChatContainer → InputBox → MessageBubble / MultiFoodForm        │
│  Tailwind CSS · Mobile-first · JWT auth · Local timezone         │
└────────────────────────────┬─────────────────────────────────────┘
                             │ HTTP/JSON
┌────────────────────────────▼─────────────────────────────────────┐
│                     FastAPI Backend (async)                       │
│                                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │ Auth Router  │  │ Food Router  │  │ Agent Router │            │
│  │ /auth/*      │  │ /foods/*     │  │ /agent/chat  │            │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘            │
│         │                 │                 │                     │
│  ┌──────▼─────────────────▼─────────────────▼───────────────┐    │
│  │                   Service Layer                           │    │
│  │  AuthService · FoodResolverService · AgentService         │    │
│  │  EmbeddingService · RerankService · SearchAnalytics       │    │
│  │  FoodUnitsService                                         │    │
│  └──────────────────────────┬────────────────────────────────┘    │
│                             │                                     │
│  ┌──────────────────────────▼────────────────────────────────┐    │
│  │              SQLAlchemy 2.0 (async) + Alembic             │    │
│  │  9 models · asyncpg driver · selectinload for N+1        │    │
│  └──────────────────────────┬────────────────────────────────┘    │
└─────────────────────────────┼────────────────────────────────────┘
                              │
               ┌──────────────▼──────────────┐
               │     PostgreSQL 14+          │
               │  pg_trgm · pgvector         │
               │  8,058 USDA foods           │
               │  130K+ nutrient rows        │
               └─────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
  Claude API            Cohere API           Ollama (local)
  (food parsing,        (Rerank 3,           (nomic-embed-text
   conversation,         embed-english-v3)    fallback embeddings)
   summaries)
```

## Design Decisions

### 1. Flexible Schema Over Rigid Columns

Nutrients, goals, and meals are stored as **data rows**, not hardcoded columns:

- `nutrients` table: 18 standard + unlimited user-defined (WW points, net carbs, etc.)
- `user_goals` table: key-value pairs (`goal_type → target_value`) — track anything
- `meals` table: 4 standard + user-defined custom meals

**Why:** Nutrition tracking is personal. Some users count macros, others track WW points, others care about micronutrients. A column-per-metric schema would require migrations for every new metric.

### 2. Hybrid Search (Trigram + Semantic + Rerank)

Food search uses three layers:

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Trigram** | pg_trgm GIN index | Typo-tolerant text matching ("chiken" → "chicken") |
| **Semantic** | Cohere embed-english-v3 / Ollama nomic-embed-text | Conceptual matching ("morning drink" → "coffee") |
| **Rerank** | Cohere Rerank 3 | Re-score top candidates for final ranking |

Strategy is configurable via `config.toml`:
- `word_count` (default): only rerank multi-word queries
- `confidence`: rerank when top hybrid score is below threshold
- `always` / `never`: force behavior

Embedding vectors are 768-dimensional, stored in pgvector columns. **Each provider gets its own column** — vectors from different models are not interchangeable.

### 3. Conversational Agent with Tool Calling

The agent uses Claude's multi-turn tool-calling protocol:

```
User message → Claude → [tool_call] → execute → [tool_result] → Claude → response
```

**7 tools:** `log_food`, `search_foods`, `resolve_foods_nl`, `list_logs`, `get_daily_summary`, `delete_log`, `show_confirmation_form`

Conversation history is kept in-memory with 60-minute expiration. This is a known limitation — database persistence is planned.

### 4. Multi-Food Confirmation Flow

When the user mentions multiple foods, the system:

1. Parses natural language via Claude into individual food items
2. Fuzzy-matches each against the database (trigram + semantic)
3. Deduplicates results (prefers human-readable portions like "1 medium apple / 182g" over generic "100g")
4. Returns a `MultiFoodConfirmationResponse` with per-item alternatives
5. Frontend renders an editable form (quantities, units, meal)
6. On submit, `POST /logs/batch` creates all entries in a single transaction

### 5. Async-First Architecture

Every I/O operation is async:
- **Database:** asyncpg + SQLAlchemy async sessions
- **AI calls:** Anthropic async client
- **Embeddings:** httpx async for Cohere/Ollama
- **Password hashing:** bcrypt runs in thread pool to avoid blocking

### 6. Single-Server Deployment

FastAPI serves both the API and the built Svelte frontend (`frontend/dist/` mounted as static files). No reverse proxy required for development; production can add nginx if needed.

### 7. Unit & Portion System

Each food can have multiple `FoodPortion` records (from USDA household measures):
- Mass units (g, oz, lb, kg) are always available
- Volume units (cup, tbsp) shown only if the food has volume portions
- Descriptive units (slice, piece, large) shown only if present in USDA data

The `FoodUnitsService` resolves user input like "3 large eggs" → 3 × 50g by matching against portion records.

### 8. Search Selection Analytics

Every time a user selects a food from search results, the system logs:
- The query text
- Which food was selected
- Where that food ranked in trigram, semantic, and hybrid results

This data enables future search quality improvements and ML-based personalization.

## Key Files

| Area | Path | Purpose |
|------|------|---------|
| Models | `whati8/models/*.py` | 9 SQLAlchemy models (User, Food, FoodLog, etc.) |
| Schemas | `whati8/schemas/*.py` | Pydantic v2 request/response validation |
| Services | `whati8/services/*.py` | Business logic (auth, resolver, agent, embeddings, rerank) |
| Routes | `whati8/api/routers/*.py` | FastAPI endpoints (auth, food, food_log, agent) |
| Config | `whati8/config.py` + `config.toml` | Pydantic Settings (.env) + TOML for search tuning |
| Frontend | `frontend/src/` | Svelte 4 + Tailwind (components, stores, API clients) |
| Migrations | `alembic/versions/` | Schema versioning (4 migrations) |
| Scripts | `scripts/` | DB setup, USDA import, embedding generation, test runners |

## Security Model

- **Authentication:** JWT (HS256, 24h expiry) via FastAPI OAuth2 password flow
- **Authorization:** All data endpoints enforce `user_id` scoping — users see only their own data
- **Rate limiting:** slowapi — 10 req/min general, 5 req/min for AI endpoints
- **Input sanitization:** AI inputs stripped of prompt injection patterns
- **CORS:** Configurable allowed origins
- **Password storage:** bcrypt 4.0.1 (passlib compatibility)
- **JWT secret:** Validated at startup for minimum entropy (32+ chars, 10+ unique)

## Database Diagram

```
users ──┬── user_goals (key-value nutrition targets)
        ├── food_logs ──── foods ──┬── food_nutrients ── nutrients
        ├── recipes                ├── food_portions
        │     └── recipe_ingredients ──┘
        └── meals (standard + custom)

foods ── search_selections (analytics)
foods ── pgvector embeddings (cohere_embedding, ollama_embedding columns)
```

## External Dependencies

| Service | Purpose | Fallback |
|---------|---------|----------|
| Anthropic Claude | Food parsing, conversation, summaries | None (core requirement) |
| Cohere Embed v3 | Semantic embeddings (768d) | Ollama nomic-embed-text |
| Cohere Rerank 3 | Search result re-ranking | Disabled (trigram + semantic only) |
| USDA FoodData Central | Bulk food/nutrient data | None (imported at setup) |
