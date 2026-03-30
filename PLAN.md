# PLAN.md — Dev/Staging Environment + Performance Fixes

## Goal
1. Set up a proper staging environment on Fly.io so changes are tested before hitting prod
2. Implement batch summary endpoint + user config caching to fix the performance problem
3. Verify performance in staging before promoting to prod

## Environment Architecture

```
Local (NUC)          Staging (Fly)           Production (Fly)
─────────────        ──────────────          ─────────────────
localhost:9428       whati8-staging.fly.dev  whati8.app
postgres:5432        whati8-staging-db       whati8-db
ENVIRONMENT=dev      ENVIRONMENT=staging     ENVIRONMENT=prod
─────────────        ──────────────          ─────────────────
     │                      │                       │
     └── git push ──→ feature branch ──→ main branch
                       auto-deploy          manual promote
```

## Steps

### Step 1: Create Staging Environment on Fly.io
**Create a separate Fly app + DB for staging.**

- `fly apps create whati8-staging`
- `fly postgres create --name whati8-staging-db --region dfw --vm-size shared-cpu-1x --volume-size 1`
- `fly postgres attach whati8-staging-db --app whati8-staging`
- Create `fly.staging.toml` (same as fly.toml but app=whati8-staging, ENVIRONMENT=staging)
- Import DB dump to staging: `pg_dump` local → restore to staging DB
- Set secrets on staging (same keys as prod)
- Deploy to staging: `fly deploy -c fly.staging.toml`
- Verify: `https://whati8-staging.fly.dev/health`

**Acceptance criteria:**
- Staging app running at whati8-staging.fly.dev
- Staging has its own isolated database with USDA data
- `fly.staging.toml` exists and is separate from `fly.toml`
- Staging uses ENVIRONMENT=staging (docs enabled, registration enabled for testing)

### Step 2: Deployment Workflow
**Establish dev → staging → prod promotion flow.**

- Feature branches deploy to staging for testing
- Deploy to staging: `fly deploy -c fly.staging.toml`
- Deploy to prod: `fly deploy -c fly.toml` (requires Aaron's approval)
- Add `scripts/deploy-staging.sh` and `scripts/deploy-prod.sh` helper scripts
- Document the workflow in `docs/DEPLOYMENT.md`

**Acceptance criteria:**
- `scripts/deploy-staging.sh` works
- `scripts/deploy-prod.sh` includes a confirmation prompt
- Deployment docs written

### Step 3: Batch Summary Endpoint
**Replace N individual /foods/{id}/summary calls with one batch call.**

- Backend: `POST /api/v1/foods/batch-summary` — accepts array of {food_id, quantity}, loads all foods in one query, computes all summaries with one config load
- Frontend: `summaryBatch.ts` — collects individual requests over a 50ms window, fires one batch call
- Update `FoodSummary.svelte` to use batched fetcher
- Cap at 50 items per batch request

**Acceptance criteria:**
- Batch endpoint returns correct summaries (matches individual endpoint results)
- Frontend batches requests automatically (transparent to components)
- 10 food items load summaries in <500ms on staging
- Individual endpoint still works (backward compatible)
- Tests pass for batch endpoint

### Step 4: User Config Caching
**Cache the user's summary config to avoid repeated DB queries.**

- The `_ensure_defaults()` call in `compute_food_summary` hits the DB every time
- Add a request-scoped or short-TTL cache for user summary config
- Option A: Pass config through from caller (batch endpoint already does this)
- Option B: `functools.lru_cache` with TTL on config lookup
- Option A is simpler since batch endpoint already loads config once

**Acceptance criteria:**
- Batch endpoint loads user config exactly once per request (not per food item)
- Individual summary endpoint benefits from caching too
- No stale config issues (cache invalidated on config update)

### Step 5: Performance Validation on Staging
**Benchmark before and after on staging.**

- Measure: time for 10 food items to show nutrition badges
- Measure: `/foods/batch-summary` response time with 10 items
- Compare: individual calls vs batch call latency
- Target: <500ms for 10 items (down from 10-50s)
- Test on staging, get Aaron's approval, then promote to prod

**Acceptance criteria:**
- Benchmark results documented
- Aaron verifies staging performance is acceptable
- Only then: deploy to prod with Aaron's explicit approval

## Files

- `fly.staging.toml` — Staging Fly config
- `scripts/deploy-staging.sh` — Staging deploy helper
- `scripts/deploy-prod.sh` — Prod deploy helper (with confirmation)
- `docs/DEPLOYMENT.md` — Deployment workflow docs
- `whati8/api/routers/food.py` — Batch summary endpoint
- `frontend/src/lib/api/summaryBatch.ts` — Frontend request batcher
- `frontend/src/lib/components/FoodSummary.svelte` — Use batched fetcher
- `tests/test_batch_summary.py` — Batch endpoint tests
