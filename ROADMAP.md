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
- [ ] Search USDA or app DB (existing hybrid search + rerank)
- [ ] Enter manually (key nutrients required, others optional, custom nutrients supported)
- [ ] User food profile table (`user_foods`) — personal library of registered foods
- [ ] Completeness indicator (rich USDA data vs sparse manual entry)

**📝 Log a Food**
- [ ] Search-as-you-type from profile foods only (small set, instant, no AI needed)
- [ ] Inline fallback: "Not in your foods? Search USDA →" (register + log in one flow)
- [ ] Recent/frequent foods section at top (tap to re-log)
- [ ] "Copy yesterday's [meal]" shortcut
- [ ] Quantity + unit selector (reuse existing smart unit system)
- [ ] Meal assignment (Breakfast/Lunch/Dinner/Snack + custom)

**📋 View Logs (Daily View)**
- [ ] Default: today. Prev/next day arrows + calendar picker
- [ ] Grouped by meal, with times
- [ ] Inline edit (tap to change quantity, meal, or delete)
- [ ] Daily summary bar at bottom — customizable nutrients (maps to `user_goals`)

### Phase 3b: Dashboard & Reports

- [ ] Daily nutrition dashboard (`GET /dashboard/today`, `/dashboard/week`)
- [ ] Macro breakdown with progress bars against goals
- [ ] Weekly/monthly trend charts
- [ ] Goal management CRUD (calories, protein, WW points, custom)
- [ ] Meal management CRUD (custom meals beyond standard 4)
- [ ] Recipe management CRUD (composed of profile foods)

### Phase 3c: Photo Recognition

- [ ] "Snap your plate" — camera capture in Add or Log flow
- [ ] Claude Vision API for food identification
- [ ] Returns suggested foods → user confirms/edits → registers or logs
- [ ] Works for nutrition labels too (extract macros from photo)

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

- [ ] Test coverage — need integration tests against test DB (currently unit + edge case only)
- [ ] Branded food data — only USDA Foundation + SR Legacy; no grocery products
- [ ] Config consolidation — some in `.env`, some in `config.toml`
- [ ] Frontend CI — no build pipeline; manual `npm run build`
- [ ] API versioning — no `/v1/` prefix yet

---

*Last updated: 2026-03-02*
