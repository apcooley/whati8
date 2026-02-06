# whati8

**AI-powered food and nutrition tracker**

## Technology Stack

| Component          | Technology                 | Notes                                         |
|:-------------------|:---------------------------|:----------------------------------------------|
| **Backend**        | Python, FastAPI            | High-performance API layer.                   |
| **Database**       | SQLAlchemy (ORM)           | For robust, idiomatic database interaction.   |
| **Data Source**    | USDA Food Data Central     | Core nutrition data provider.                 |
| **AI/LLM**         | Anthropic Claude (default) | Natural language food parsing and resolution. |
| **Authentication** | FastAPI OAuth2 + JWT       | Secure user session management.               |

---

## Key Features

*   **Easy To Use:** Unlike other products which require a lot of typing, searching, and fiddling, you just type in natural text, dictate with voice, or even snap a pic of your food and it does the rest.
*   **Highly Customizable**: Add your own foods, recipes, meals, and nutrition tracking methodology (caliories, protein, weight watchers, etc.). whati8 molds to your approach.
*   **Database Search:** Utilizing optimized database queries and fuzzy matching for rapid food lookup. Starts with over 50,000 foods already loaded.
*   **Personalized Goals:** Adherence to user-defined macro targets (Protein, Carbs, Fat) and daily calorie budgets (Default: ~1850 kcal).
*   **Secure & Scalable:** Built on a modern Python stack for maintainability and growth.

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
JWT_SECRET=your-secret-key-change-in-production-use-openssl-rand-hex-32
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Application
DEBUG=true
LOG_LEVEL=info
```

**Note:** Never commit `.env` to version control. A `.env.example` template is provided.

### 5. Database Setup

**Create the PostgreSQL database:**
```bash
# Using createdb (if you have PostgreSQL installed locally)
createdb whati8

# Or using psql
psql -U postgres -c "CREATE DATABASE whati8;"
psql -U postgres -c "CREATE USER whati8 WITH PASSWORD 'whati8';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE whati8 TO whati8;"
```

**Initialize schema with migrations:**
```bash
# Once Alembic is configured (coming in Phase 1)
alembic upgrade head
```

**Import USDA Food Data:**
```bash
# Management script for bulk import (coming in Phase 1)
uv python -m whati8.cli import-usda-data
```

*Note: Initial USDA data import downloads ~500MB and takes 5-10 minutes. You'll need your USDA API key configured in `.env`.*

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

## Roadmap & Next Steps

1.  **Phase 1: Core Logging & Search** *(Current Phase)*
    *   ✅ Project structure and README
    *   ⬜ SQLAlchemy models: `User`, `Food`, `FoodLog`, `Recipe`, `UserGoal`
    *   ⬜ Database migrations (Alembic setup)
    *   ⬜ USDA bulk data import script
    *   ⬜ Authentication endpoints (`/register`, `/login`, `/me`)
    *   ⬜ Food search endpoint (`/foods/search`) with fuzzy matching
    *   ⬜ AI agent for natural language food resolution (`/resolve`)
    *   ⬜ Logging endpoints (`/logs` - CRUD operations)
    *   ⬜ Daily nutrition dashboard (`/dashboard/today`)
2.  **Phase 2: UI**
    *   Create a basic web UI to allow the user to chat with the agent.
    *   Add voice-based requests.
    *   Add recipe OCR and food recognition technology via photo.
3.  **Phase 3: Production Ready**
    *   Tighten the UX
    *   Harden security requirements
    *   Ensure scalability
    *   Deploy to cloud
    *   Alpha and Beta test
