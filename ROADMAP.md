# Roadmap

## Completed

### Phase 1: Core Logging & Search ✅
- Flexible database schema (9 tables, async SQLAlchemy 2.0)
- JWT authentication (register, login, CLI + API)
- USDA data import (8,058 foods, 130K+ nutrient relationships)
- Fuzzy food search (pg_trgm trigram indexes)
- AI food resolution (Claude parses natural language → DB matches)
- Food logging CRUD with user isolation

### Phase 2: Conversational UI ✅
- Conversational agent with 7 tools (Claude multi-turn tool calling)
- Svelte 4 + Tailwind frontend (mobile-first, JWT auth)
- Multi-food confirmation form (editable quantities, smart unit dropdowns)
- Batch-summary endpoint (log + calculate + Claude-formatted summary)
- Smart deduplication (prefers human-readable portions)
- Custom food creation (user-defined foods with nutrition data)
- Local timezone display throughout

### Phase 2.5: Search Quality ✅
- Semantic embeddings (Cohere embed-english-v3 primary, Ollama fallback)
- pgvector integration (768d vectors, dual-column per provider)
- Hybrid search (keyword weight + semantic weight, configurable in config.toml)
- Cohere Rerank 3 integration (word-count / confidence / always / never strategies)
- Search selection analytics (logs ranking position across all search methods)

---

### Phase 2.7: Data Quality & Nutrition Accuracy (Mar 2026) ✅
- Energy stored as kcal throughout (purged all kJ conversion code from 6 files)
- Energy coalesce: COALESCE(Atwater General 199, Atwater Specific 200, Plain Energy 39)
- Carb coalesce: COALESCE(by summation 107, MAX(by difference 81, 0))
- USDA dedup integrated into import script (Foundation preferred, 73 SR Legacy dupes removed)
- Naive datetime storage: `logged_at` stores wall-clock time, not UTC
- Multi-unit serving_quantity: portions store per-unit gram_weight, amount stores default qty
- Photo capture: upload button for nutrition label photos
- Emoji nutrient display: 🔥 kcal, 🥩 protein, 🌾 fiber, 🍞 carbs, 🧈 fat
- Per-log summary nutrients matching user's display config
- Profile food search with USDA fallback
- 38 tests across 4 new test suites (kcal, coalesce, datetime, serving_quantity)

---

## Current: Phase 3 — Action-Based UI Redesign

Shift from "conversation with agent" to discrete user actions. The chat interface becomes one option, not the primary flow.

### Navigation

```
┌─────────────────────────────────────┐
│  [📝 Log]  [📋 Today]  [➕ Add]     │  ← bottom nav (primary actions)
│  [📊 Reports]  [🤖 Chat]           │  ← secondary / overflow
└─────────────────────────────────────┘
```

**Log** is the default screen (most frequent action).

### Phase 3a: Profile Foods + Log + View Logs (MVP)

The core loop: register foods once, log them fast every day, see what you ate.

**➕ Add a Food (Register to Profile)**
- [x] Search USDA or app DB (existing hybrid search + rerank)
- [x] Enter manually (key nutrients required, others optional, custom nutrients supported)
- [x] User food profile table (`user_foods`) — personal library of registered foods/recipes
- [x] Photo capture for nutrition labels (Claude Vision extraction)
- [ ] Completeness indicator (rich USDA data vs sparse manual entry)
  - red = missing key data (e.g. calories, protein, fiber, fat, carbs)
  - yellow = missing common data (e.g. cholesterol, sodium, sat fat, trans fat, sugar, serving size/unit and conversion to grams)
  - green = complete data

**📝 Log a Food**
- [x] Search-as-you-type from profile foods only (small set, instant, no AI needed)
- [x] Inline fallback: add icon on right, automatically searches
- [x] Recent/frequent foods sorted by COALESCE(last_used, created_at) — already implemented
- [x] Copy/move individual logs to any date/meal
- [x] Copy entire meal to another date
- [x] Quantity + unit selector (reuse existing smart unit system)
- [x] Meal assignment (Breakfast/Lunch/Dinner/Snack + custom)

**📋 View Logs (Daily View)**
- [x] Default: today. Prev/next day arrows + calendar picker
- [x] Grouped by meal, with times
- [x] Inline edit (tap to change quantity, meal, or delete)
- [x] Daily summary bar at bottom — customizable nutrients (emoji display, formula support)

### Phase 3b: Dashboard & Reports

- [ ] Daily nutrition dashboard (`GET /dashboard/today`, `/dashboard/week`)
- [ ] Macro breakdown with progress bars against goals
- [ ] Weekly/monthly trend charts
- [x] Goal management — configurable summary nutrients with formula support (WW points)
- [ ] Meal management CRUD (custom meals beyond standard 4)
- [x] Recipe management — versioned recipes, ingredient search, portion matching

### Phase 3c: Photo Recognition ✅ (Partial)

- [x] Camera capture in Add flow (upload button)
- [x] Claude Vision API for nutrition label extraction
- [x] Returns suggested foods → user confirms/edits → registers
- [ ] "Snap your plate" — identify foods from photos (not just labels)
- [ ] Barcode/UPC recognition from camera

### Phase 3d: Barcode Scanning

- [ ] Camera-based UPC lookup
- [ ] Data source: USDA Branded Foods (~400K items) and/or OpenFoodFacts
- [ ] Selective branded food import (by category or on-demand per scan)
- [ ] Scanned food auto-registers to profile

### Phase 3e: Voice Input

- [ ] Web Speech API for hands-free input
- [ ] Voice → text → routes to agent for parsing ("I had two eggs and toast")
- [ ] Available from Log screen and Chat tab

### 🤖 Chat with Agent (Reworked)

- [ ] Moves from primary interface to secondary tab
- [ ] Open-ended queries ("what should I eat to hit my protein goal?")
- [ ] Bulk logging ("log everything I ate at Chipotle")
- [ ] Nutrition advice and goal coaching
- [ ] Still has full tool access (search, log, summarize)

---

## Phase 4: Production Hardening

- [ ] Conversation persistence (in-memory → database-backed sessions)
- [ ] Streaming responses (SSE for agent output)
- [ ] PWA support (installable, offline queue)
- [ ] Push notifications (meal reminders, goal alerts)
- [ ] Improved error recovery (AI retry logic, graceful degradation)

## Phase 5: Social & Sharing (Optional)

- [ ] Multi-user household / shared recipes
- [ ] CSV/PDF nutrition reports export
- [ ] Multi-language support
- [ ] Public deployment with onboarding flow

---

## Technical Debt

- [x] Test coverage — 38+ integration tests against live PostgreSQL ✅
- [ ] Branded food data — only USDA Foundation + SR Legacy; no grocery products
- [ ] Config consolidation — some in `.env`, some in `config.toml`
- [ ] Frontend CI — no build pipeline; manual `npx vite build`
- [ ] API versioning — no `/v1/` prefix yet
- [ ] Seed data guard — meals table can get wiped by re-imports; need seed check on startup
- [x] Frontend local date fix — use getFullYear/getMonth/getDate instead of toISOString (UTC)
- [x] Portion description format — unit label only, no quantity prefix; backend regex safety net

---

*Last updated: 2026-03-22 (evening)*
