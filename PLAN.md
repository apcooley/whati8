# PLAN.md — Deploy whati8 to Fly.io

## Goal
Deploy whati8 (FastAPI + Postgres + Svelte frontend) to Fly.io behind `whati8.app` with real TLS, zero home IP exposure.

## Tech Stack
- **Backend:** Python 3.11, FastAPI, SQLAlchemy async, asyncpg
- **Database:** PostgreSQL 16 (Fly Postgres, 199MB USDA data)
- **Frontend:** Svelte 4, TypeScript, Vite (built into `frontend/dist/`, served by FastAPI StaticFiles)
- **Domain:** `whati8.app` (Cloudflare DNS)
- **Existing:** Dockerfile, docker-compose.yml, Alembic migrations, pyproject.toml w/ uv

## Steps

### Step 1: Fly.io Setup & Configuration
**Create Fly app + Postgres cluster + `fly.toml` config.**

- Install `flyctl` CLI
- `fly apps create whati8`
- `fly postgres create` (1GB free tier, region `den` for Denver)
- Create `fly.toml` with:
  - App name, region (`den`)
  - HTTP service on internal port 9428
  - Health check at `/health`
  - Auto-stop/start for cost savings
  - `[build]` pointing to existing Dockerfile
  - `[env]` for non-secret config (ENVIRONMENT=prod, LOG_LEVEL=info, etc.)
- Create `.dockerignore` (exclude .venv, .git, node_modules, __pycache__, .env)
- Set secrets via `fly secrets set`: JWT_SECRET, ANTHROPIC_API_KEY, FDC_API_KEY

**Acceptance criteria:**
- `fly.toml` passes `fly config validate`
- `.dockerignore` exists and excludes dev artifacts
- All secrets documented (not committed)

### Step 2: Production Database & Migrations
**Export local DB, import to Fly Postgres, verify Alembic migration state.**

- `pg_dump` local database to SQL file
- Attach Fly Postgres to the app (`fly postgres attach`)
- Import dump via `fly postgres connect` or proxy
- Verify Alembic version table is correct
- Test `/health` endpoint returns `{"status":"healthy","db":"ok"}`
- Add `DATABASE_URL` handling in config for Fly's `DATABASE_URL` env var format

**Acceptance criteria:**
- All 16 tables present in cloud DB
- Row counts match local (8060 foods, 642K food_nutrients, etc.)
- Alembic `current` shows latest migration
- Health check passes against cloud DB

### Step 3: Production Config & Security Hardening
**Ensure prod config is safe: no debug, strong JWT, CORS locked down, Swagger disabled.**

- Update `config.py` Settings to read Fly's `DATABASE_URL` (may use `postgres://` not `postgresql://`)
- Set `ENVIRONMENT=prod` (disables Swagger docs)
- Set `DEBUG=false`
- Set `ALLOWED_ORIGINS` to `["https://whati8.app"]`
- Ensure `JWT_SECRET` validation rejects weak secrets on startup
- Verify `config.toml` defaults are production-safe
- Update `BodySizeLimitMiddleware` — no changes needed (already correct)

**Acceptance criteria:**
- App starts with `ENVIRONMENT=prod` without errors
- `/docs` returns 404 (Swagger disabled)
- CORS rejects requests from non-whitelisted origins
- No debug info in error responses

### Step 4: Deploy & Smoke Test
**First deploy to Fly.io, verify all endpoints work.**

- `fly deploy` (builds Docker image, pushes, starts)
- Verify health check: `curl https://whati8.fly.dev/health`
- Test auth flow: register → login → refresh token
- Test food search: `/api/v1/foods/search?query=chicken`
- Test food logging: create/read/delete a food log
- Test photo upload: POST image to `/api/v1/photo/recognize`
- Test frontend loads at `https://whati8.fly.dev/`

**Acceptance criteria:**
- All core API endpoints return expected responses
- Frontend renders and can log food
- Photo upload works (not 413)
- No 500 errors in `fly logs`

### Step 5: Custom Domain & TLS
**Point `whati8.app` to Fly.io, provision real TLS cert.**

- `fly certs create whati8.app`
- Add DNS records in Cloudflare:
  - `CNAME @ whati8.fly.dev` (proxied OFF — Fly handles TLS)
  - Or `A` record pointing to Fly's IP
- Verify cert provisioned: `fly certs show whati8.app`
- Update `ALLOWED_ORIGINS` to include `https://whati8.app`
- Test `https://whati8.app` loads and works end-to-end

**Acceptance criteria:**
- `https://whati8.app` loads with valid TLS cert
- All API endpoints work via custom domain
- HSTS header present
- No mixed content warnings

### Step 6: CI/CD & Monitoring
**Set up GitHub Actions for automated deploy + basic monitoring.**

- Create `.github/workflows/deploy.yml`:
  - On push to `main`: run tests → build → `fly deploy`
  - Secrets: `FLY_API_TOKEN`
- Add `fly.toml` to git
- Set up Fly.io health check alerts (built-in)
- Document rollback procedure: `fly releases`, `fly deploy --image <previous>`
- Update `HARDENING_PLAN.md` with cloud deployment status

**Acceptance criteria:**
- Push to `main` triggers automated deploy
- Failed tests block deploy
- `fly status` shows healthy app
- Rollback documented and tested

## Deployment Architecture

```
User → Cloudflare DNS → Fly.io Edge (TLS) → Fly VM (whati8:9428) → Fly Postgres
                                                    ↓
                                              Frontend (static)
                                              Backend (FastAPI)
```

## Secrets (never committed)
- `JWT_SECRET` — strong random string (32+ chars)
- `ANTHROPIC_API_KEY` — for photo recognition + agent
- `FDC_API_KEY` — USDA Food Data Central
- `DATABASE_URL` — auto-set by `fly postgres attach`

## Risk Mitigation
- USDA data (190MB) must be imported to cloud DB — may take a few minutes
- Fly free Postgres is 1GB — we're at 199MB, plenty of headroom
- **Embeddings:** Already using Cohere embed-english-v3.0 as primary, Ollama as local fallback. In prod, Cohere is the only provider — add `COHERE_API_KEY` to Fly secrets. Ollama fallback will gracefully fail (no local Ollama on Fly VM).
- **Rerank:** Already using Cohere rerank API — same key covers it.
