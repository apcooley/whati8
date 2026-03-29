# PLAN.md — Phase 1: Hardening & Production Readiness

## Goal
Prepare whati8 for public deployment with API versioning, hardened auth, rate limiting,
containerization, and dev/prod separation.

## Tech Stack
- **Backend:** Python 3.11, FastAPI, SQLAlchemy (async), PostgreSQL 16
- **Frontend:** SvelteKit, TypeScript, Vite
- **Package Manager:** uv
- **Testing:** pytest (backend), vitest (frontend)
- **Linter:** ruff (Python)

## Steps

### Step 1: API Versioning + Health Check
Move all routes under `/api/v1/` prefix, add `/health` endpoint.

### Step 2: Environment Config + CORS Tightening
### Step 3: Request Body Size Limits
### Step 4: Per-IP Auth Rate Limiting
### Step 5: Refresh Tokens
### Step 6: API Keys
### Step 7: Database Backup Script
### Step 8: Containerization + Dev/Prod
### Step 9: Deployment Docs
