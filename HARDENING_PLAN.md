# whati8 - Production Hardening & Public API Plan

## Goal
Secure and stabilize the whati8 API/MCP for safe hosting on the open internet.
This expands on **Phase 4: Production Hardening** from `BUILD-PLAN.md`.

## 1. Transport Security & Infrastructure
- [ ] **TLS/SSL Termination**: Deploy behind Caddy or Nginx with Let's Encrypt.
- [ ] **HSTS Headers**: Enable `Strict-Transport-Security` to force HTTPS.
- [ ] **Security Header Audit**:
    - [x] `X-Frame-Options: DENY` (Anti-clickjacking)
    - [x] `X-Content-Type-Options: nosniff` (Anti-sniffing)
    - [x] `Content-Security-Policy` (Strict for API, relaxed for Docs)
    - [x] `X-XSS-Protection` (Legacy support)
- [ ] **IP-Based Protections**: Configure `Fail2Ban` or cloud-level WAF for brute-force mitigation on `/auth/login`.

## 2. Authentication & Authorization (IDOR Audit)
- [ ] **Systematic Ownership Check**: Audit every router to ensure `user_id` verification on all resource access (GET/PUT/DELETE).
    - [x] `food_log.py` (checked)
    - [x] `recipe.py` (checked)
    - [ ] `profile.py` (needs audit)
    - [ ] `summary_config.py` (needs audit)
    - [ ] `photo.py` (needs audit)
- [ ] **API Key Scoping**: (Future) Allow keys to be "read-only" or "search-only".
- [ ] **Rate Limit Tuning**: Verify limits for public endpoints (currently 10/min general, 5/min AI).

## 3. Configuration & Secrets
- [ ] **Consolidate Config**: Move `config.toml` logic into Pydantic `Settings` in `whati8/config.py`.
- [ ] **Startup Guard**: Re-validate `JWT_SECRET` strength on startup (min length, uniqueness).
- [ ] **Environment Separation**: Ensure `ENVIRONMENT=prod` strictly disables debug features and Swagger docs (defaulting to False).

## 4. Database & Data Integrity
- [ ] **Seed Data Guard**: Ensure standard `meals` (Breakfast, Lunch, Dinner, Snack) are present without being destructive on re-import.
- [ ] **Migration Safety**: Verify all migrations are reversible and tested against a copy of production data.
- [ ] **Connection Hardening**: Ensure Postgres is bound only to `localhost` or internal Docker network.

## 5. Observability & Operations
- [ ] **Structured JSON Logging**: Switch to JSON format in production for easier log parsing (Logstash/Grafana).
- [ ] **Error Tracking**: Integrate **Sentry** or similar for real-time error reporting.
- [ ] **Backup Validation**: Automated weekly "restore test" to verify database backups actually work.

## 6. MCP & Agent Safety
- [ ] **Conversation Persistence**: Move agent memory from in-memory dict to the database (linked to `user_id`).
- [ ] **Output Scrubbing**: Ensure agent/tool responses don't leak internal DB IDs, file paths, or sensitive system metadata.
- [ ] **Streaming (SSE)**: Implement Server-Sent Events for long-running AI operations to prevent request timeouts.

## 7. Technical Debt (Hardening related)
- [ ] **Pydantic V2 Migration**: Replace all class-based `Config` with `ConfigDict`.
- [ ] **Frontend Build CI**: Automate `vite build` and linting on push to ensure production assets are always valid.
- [ ] **Comprehensive Integration Suite**: Expand `tests/` to cover full "User A vs User B" isolation scenarios.
