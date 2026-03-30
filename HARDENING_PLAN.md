# whati8 - Production Hardening & Public API Plan

*Updated: 2026-03-29*

## Goal
Secure and stabilize the whati8 API/MCP for safe hosting on the open internet.

---

## 1. Transport Security & Infrastructure

| Item | Status |
|:--|:--|
| TLS/SSL Termination (Caddy reverse proxy) | ✅ Done — self-signed on LAN, Caddy live |
| HSTS Headers (`Strict-Transport-Security`) | ✅ Done — `max-age=31536000; includeSubDomains` |
| `X-Frame-Options: DENY` | ✅ Done |
| `X-Content-Type-Options: nosniff` | ✅ Done |
| `Content-Security-Policy` (strict for API, relaxed for docs) | ✅ Done (backend) |
| `X-XSS-Protection` | ✅ Done |
| `Referrer-Policy` | ✅ Done |
| Server header removed | ✅ Done (`-Server` in Caddyfile) |
| HTTP → HTTPS redirect | ✅ Done |
| Domain + Let's Encrypt | ⬜ Pending — waiting on domain purchase |
| IP-based brute-force protection (Fail2Ban or WAF) | ⬜ Pending |

**Test coverage:** 18 integration tests (`tests/test_caddy_proxy.py`)

---

## 2. Configuration & Secrets

| Item | Status |
|:--|:--|
| Config consolidation (`.env` + `config.toml` → Pydantic Settings) | ✅ Done |
| `env_nested_delimiter="__"` for nested env overrides | ✅ Done |
| TOML loaded via custom `TomlConfigSettingsSource` with caching + error handling | ✅ Done |
| Search weight validation (0.0–1.0 bounds) | ✅ Done |
| Startup guard for weak `JWT_SECRET` | ✅ Done (min length + uniqueness) |
| `ENVIRONMENT=prod` disables Swagger docs | ✅ Done |
| Pydantic V2 migration (`ConfigDict`) | ✅ Done |

**Test coverage:** 9 tests (`tests/test_config_consolidation.py`)

---

## 3. Authentication & Authorization

| Item | Status |
|:--|:--|
| JWT + refresh token rotation | ✅ Done (pre-existing) |
| API key auth (`wi8_*` prefix, `X-API-Key` header) | ✅ Done (pre-existing) |
| Rate limiting (10/min general, 5/min AI, 5/min login, 3/min register) | ✅ Done |
| IDOR audit — `food_log.py` ownership checks | ✅ Verified |
| IDOR audit — `recipe.py` ownership checks | ✅ Verified |
| IDOR audit — `profile.py` ownership checks | ✅ Verified |
| IDOR audit — `summary_config.py` ownership checks | ✅ Verified |
| IDOR audit — `photo.py` (no user data returned) | ✅ Verified |
| API key scoping (read-only keys) | ⬜ Future |
| Cross-user isolation test suite | ⬜ Pending |

---

## 4. Request Handling & Body Limits

| Item | Status |
|:--|:--|
| Global body size limit (1MB) via `BodySizeLimitMiddleware` | ✅ Done |
| Photo upload exempt (10MB) via path-based override | ✅ Done |
| Caddy `request_body max_size 1MB` (belt-and-suspenders) | ✅ Done |

**Test coverage:** Backend 413 test in `test_caddy_proxy.py`

---

## 5. Database & Data Integrity

| Item | Status |
|:--|:--|
| Alembic migrations | ✅ Done (pre-existing) |
| Backup script (`scripts/backup_db.sh`) | ✅ Done (pre-existing) |
| Postgres bound to localhost only | ✅ Verified |
| Seed data guard (meals table) | ⬜ Pending |
| Migration reversibility testing | ⬜ Pending |
| Automated backup restore test | ⬜ Pending |

---

## 6. Frontend & Dev Tooling

| Item | Status |
|:--|:--|
| Unified `FoodEntryForm` (manual + photo) | ✅ Done |
| Shared nutrient constants (`lib/constants/nutrients.ts`) | ✅ Done |
| Vite proxy fixed (`/api` catch-all) | ✅ Done |
| Photo API path corrected (`/api/v1/photo/recognize`) | ✅ Done |
| `allowedHosts: true` for Tailscale dev access | ✅ Done |
| Frontend CI (build + lint on push) | ⬜ Pending |

---

## 7. MCP & Agent Safety

| Item | Status |
|:--|:--|
| Conversation persistence (in-memory → DB) | ⬜ Pending |
| Output scrubbing (no internal paths/IDs leaked) | ⬜ Pending |
| Streaming (SSE) for long-running AI ops | ⬜ Pending |

---

## 8. Observability & Operations

| Item | Status |
|:--|:--|
| Caddy access logging with rotation | ✅ Done |
| Structured JSON logging (production) | ⬜ Pending |
| Error tracking (Sentry or similar) | ⬜ Pending |
| Automated backup restore validation | ⬜ Pending |

---

## 9. Test Health

| Metric | Value |
|:--|:--|
| **Total tests** | 468 |
| **Passing** | 468 |
| **Failing** | 0 |
| **Skipped** | 0 |
| **Backend (pytest)** | 468 |
| **Frontend (vitest)** | 129 passing, 3 pre-existing failures (nutrientBadges) |
| **Rate-limit flakes** | Fixed — module-scoped auth token |
| **Async SQLAlchemy skip** | Fixed — `db.expire_all()` + `selectinload(portions)` |

---

## Priority Queue (Next Up)

1. **Cross-user isolation test suite** — dedicated IDOR tests for every router
2. **Domain + Let's Encrypt** — one-line Caddyfile change when domain is ready
3. **Conversation persistence** — agent memory from dict → database
4. **Structured JSON logging** — for production log aggregation
5. **Frontend CI** — automated build + lint on push
