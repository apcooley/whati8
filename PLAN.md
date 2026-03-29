# PLAN.md — Config Consolidation

## Goal
Consolidate `config.toml` logic into the Pydantic `Settings` class in `whati8/config.py` to have a single source of truth for all application settings.

## Tech Stack
- Python 3.11
- Pydantic Settings v2
- Pytest

## Steps

### Step 1: Refactor `whati8/config.py`
- Define `SearchSettings` and `RerankSettings` Pydantic models.
- Add them to the main `Settings` class as nested fields.
- Implement a `model_validator` or logic in `__init__` to load values from `config.toml` (if present) as defaults.
- Remove `load_config()` and `app_config` global.

### Step 2: Update Services
- **`whati8/services/rerank_service.py`**: Update `rerank_food_matches` to use `settings.search.rerank` instead of `app_config`.
- **`whati8/services/food_resolver.py`**: Pull `KEYWORD_WEIGHT` and `SEMANTIC_WEIGHT` from `settings.search`.
- **`whati8/services/search_analytics.py`**: Update hardcoded weights to use `settings.search`.

### Step 3: Verification & Cleanup
- Add a test in `tests/test_config.py` to verify `config.toml` values are correctly picked up.
- Remove `config.toml` (or keep as a template?) — actually, the goal is "config consolidation", so we might want to move those into `.env` or just keep the defaults in code and allow overrides via env vars.
- Update `README.md` or `DEPLOYMENT.md` if needed.
