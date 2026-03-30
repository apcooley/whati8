# Deployment Guide

This document describes the deployment workflow for whati8, covering local development, staging, and production environments.

---

## Environment Overview

| Environment | App Name         | URL                            | Auto-stop  | Registration | Docs  |
|-------------|------------------|--------------------------------|------------|--------------|-------|
| Development | (local)          | http://localhost:9428          | N/A        | Enabled      | On    |
| Staging     | whati8-staging   | https://whati8-staging.fly.dev | `suspend`  | Enabled      | On    |
| Production  | whati8-app       | https://whati8.app             | `off`      | Disabled     | Off   |

---

## Local Development Setup

1. **Clone the repo:**
   ```bash
   git clone https://github.com/aaroncooley/whati8.git
   cd whati8
   ```

2. **Install dependencies:**
   ```bash
   uv sync
   ```

3. **Set environment variables:**
   Copy `.env.example` to `.env` and fill in values:
   ```bash
   cp .env.example .env
   ```

4. **Run the development server:**
   ```bash
   uv run uvicorn whati8.main:app --reload --port 9428
   ```

5. **Run tests:**
   ```bash
   uv run pytest
   ```

---

## Deploying to Staging

Staging is used for testing feature branches before merging to `main`. It mirrors production configuration but with registration and docs enabled.

**Configuration:** `fly.staging.toml`

### Automatic (via script):
```bash
./scripts/deploy-staging.sh
```

### Manual:
```bash
fly deploy -c fly.staging.toml
```

### Recommended workflow:
1. Create a feature branch: `git checkout -b feature/my-feature`
2. Push your changes and test locally
3. Deploy to staging: `./scripts/deploy-staging.sh`
4. Verify at https://whati8-staging.fly.dev/
5. Open a PR for review

---

## Promoting to Production

Production deployment requires explicit confirmation. **Never deploy untested code to production.**

**Configuration:** `fly.toml`

### Via script (recommended — includes safety prompt):
```bash
./scripts/deploy-prod.sh
```

### Manual:
```bash
fly deploy -c fly.toml
```

> ⚠️ The prod deploy script will prompt for confirmation before proceeding.

### Pre-deployment checklist:
- [ ] All tests pass: `uv run pytest`
- [ ] Changes validated on staging
- [ ] PR reviewed and merged to `main`
- [ ] No secrets committed to the repo

---

## Rollback Procedure

If a production deployment goes wrong, roll back to the previous image:

1. **List recent releases:**
   ```bash
   fly releases -a whati8-app
   ```

2. **Identify the last good image** (e.g., `registry.fly.io/whati8-app:deployment-XXXXXXXX`)

3. **Deploy that image directly:**
   ```bash
   fly deploy --image registry.fly.io/whati8-app:deployment-XXXXXXXX -a whati8-app
   ```

For staging rollbacks, replace `-a whati8-app` with `-a whati8-staging`.

---

## Secrets Management

Secrets (API keys, JWT secret, database URL) are **never stored in `fly.toml` or `fly.staging.toml`**. They are managed via Fly's secret store.

### Set a secret:
```bash
# Production
fly secrets set JWT_SECRET=<value> -a whati8-app

# Staging
fly secrets set JWT_SECRET=<value> -a whati8-staging
```

### List secrets (names only, values hidden):
```bash
fly secrets list -a whati8-app
```

### Required secrets:
| Secret           | Description                        |
|------------------|------------------------------------|
| `DATABASE_URL`   | PostgreSQL connection string       |
| `JWT_SECRET`     | Secret key for JWT token signing   |
| `ANTHROPIC_API_KEY` | Anthropic API key (if used)     |
| `COHERE_API_KEY` | Cohere API key (if used)           |

> **Never commit secrets to git.** Use `fly secrets set` or the Fly dashboard.

---

## Configuration Differences

| Setting            | Development     | Staging                            | Production              |
|--------------------|-----------------|------------------------------------|-------------------------|
| `ENVIRONMENT`      | `dev`           | `staging`                          | `prod`                  |
| `LOG_LEVEL`        | `debug`         | `info`                             | `info`                  |
| `REGISTRATION_ENABLED` | `true`      | `true`                             | `false`                 |
| `ALLOWED_ORIGINS`  | `*` / localhost | `whati8-staging.fly.dev, localhost` | `whati8.app`           |
| `auto_stop`        | N/A             | `suspend` (saves cost)             | `off` (always on)       |
| Secrets            | `.env` file     | `fly secrets` (staging app)        | `fly secrets` (prod app)|
