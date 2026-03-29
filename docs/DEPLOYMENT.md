# Deployment Guide

## Quick Start (Docker)

```bash
# 1. Copy environment file
cp .env.example .env
# Edit .env with your secrets (JWT_SECRET, DB_PASSWORD, etc.)

# 2. Start production
docker compose up -d

# 3. Run migrations
docker compose exec app uv run alembic upgrade head

# 4. Verify
curl http://localhost:9428/health
```

## Development

```bash
# Start dev environment (port 9429, hot reload, separate DB)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Run tests
docker compose exec app uv run pytest -q

# Logs
docker compose logs -f app
```

## Bare Metal (no Docker)

```bash
# 1. Install dependencies
uv sync

# 2. Set up PostgreSQL
createdb whati8
createuser whati8

# 3. Configure
cp .env.example .env
# Edit .env

# 4. Run migrations
uv run alembic upgrade head

# 5. Start server
uv run python -m whati8 serve

# 6. (Optional) systemd service
cp whati8.service ~/.config/systemd/user/
systemctl --user enable --now whati8
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✅ | — | PostgreSQL connection string |
| `JWT_SECRET` | ✅ | — | Secret for JWT signing (32+ chars, 10+ unique) |
| `ENVIRONMENT` | ❌ | `dev` | `dev`, `staging`, or `prod` |
| `ALLOWED_ORIGINS` | ❌ | localhost | CORS origins (JSON array) |
| `DB_PASSWORD` | ❌ | `whati8` | Database password (Docker) |
| `ANTHROPIC_API_KEY` | ❌ | — | For AI food resolution |
| `USDA_API_KEY` | ❌ | — | For USDA food search |
| `RATE_LIMIT_ENABLED` | ❌ | `true` | Enable rate limiting |
| `RATE_LIMIT_PER_MINUTE` | ❌ | `10` | General API rate limit |
| `RATE_LIMIT_AI_PER_MINUTE` | ❌ | `5` | AI endpoint rate limit |
| `JWT_EXPIRATION_HOURS` | ❌ | `1` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRATION_DAYS` | ❌ | `30` | Refresh token lifetime |
| `MAX_BODY_SIZE` | ❌ | `1048576` | Max request body (bytes) |
| `DOCS_ENABLED` | ❌ | auto | Swagger docs (auto: on for dev, off for prod) |

## Database

### Backups

```bash
# Manual backup
./scripts/backup_db.sh

# Restore from backup
./scripts/restore_db.sh /var/backups/whati8/whati8_20260329_030000.sql.gz

# Cron (daily at 3 AM)
echo "0 3 * * * /path/to/whati8/scripts/backup_db.sh" | crontab -
```

### Migrations

```bash
# Apply all migrations
uv run alembic upgrade head

# Check current version
uv run alembic current

# Generate new migration
uv run alembic revision --autogenerate -m "description"
```

## API Authentication

### JWT (browser clients)
```bash
# Login
curl -X POST http://localhost:9428/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"login": "user", "password": "pass"}'

# Use access_token
curl http://localhost:9428/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"

# Refresh when expired
curl -X POST http://localhost:9428/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<refresh_token>"}'
```

### API Keys (scripts, MCP, automation)
```bash
# Create key (requires JWT auth)
curl -X POST http://localhost:9428/api/v1/auth/api-keys \
  -H "Authorization: Bearer <jwt>" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Script"}'

# Use via Bearer
curl http://localhost:9428/api/v1/foods/search?q=egg \
  -H "Authorization: Bearer wi8_<key>"

# Or via X-API-Key header
curl http://localhost:9428/api/v1/foods/search?q=egg \
  -H "X-API-Key: wi8_<key>"
```

## Production Checklist

- [ ] Set `ENVIRONMENT=prod`
- [ ] Set strong `JWT_SECRET` (32+ chars, random)
- [ ] Set `ALLOWED_ORIGINS` to your domain
- [ ] Set unique `DB_PASSWORD`
- [ ] Configure daily backup cron
- [ ] Set up TLS (Caddy, cloud LB, or Cloudflare)
- [ ] Review rate limits for expected traffic
- [ ] Verify `/health` endpoint responds
- [ ] Swagger docs disabled (`/api/v1/docs` returns 404)

## Architecture

```
Client → [TLS Termination] → whati8 (FastAPI/uvicorn :9428) → PostgreSQL
                                ↑
                          Middleware stack:
                          1. Body size limit
                          2. Security headers
                          3. CORS
                          4. Rate limiting
```

### Dev vs Prod

| | Dev | Prod |
|---|---|---|
| Port | 9429 | 9428 |
| DB | whati8_dev | whati8 |
| Hot reload | ✅ | ❌ |
| Swagger docs | ✅ | ❌ |
| CORS | localhost allowed | explicit origins only |
| Restart | manual | always |
