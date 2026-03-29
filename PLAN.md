# PLAN.md — Caddy TLS Reverse Proxy

## Goal
Set up Caddy as a reverse proxy in front of whati8, terminating TLS with a self-signed cert for internal/testing use. When a domain is secured later, switching to Let's Encrypt is a one-line change.

## Tech Stack
- Caddy 2.x (already installed at /usr/local/bin/caddy)
- whati8 running on localhost:9428 (systemd user service)
- Self-signed TLS for 192.168.1.11
- Python tests to verify the proxy works

## Steps

### Step 1: Write Caddyfile + HSTS config + test suite
- Write `/home/aaron/source/whati8/deploy/Caddyfile` for internal TLS proxy
- Write tests that verify: reverse proxy works, TLS terminates, security headers present, HSTS set, Swagger docs blocked in prod mode
- Update CORS allowed_origins in .env to include https://192.168.1.11

### Step 2: Deploy Caddyfile to system Caddy
- Copy Caddyfile to /etc/caddy/Caddyfile
- Restart Caddy service
- Run tests against live proxy
- Update DEPLOYMENT.md with Caddy instructions

### Step 3: Verify end-to-end + document domain migration path
- Smoke test full flow through Caddy (health check, auth, food search)
- Document how to switch from self-signed to Let's Encrypt when domain is ready
- Update HARDENING_PLAN.md checklist
