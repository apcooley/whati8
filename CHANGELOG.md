# Changelog

All notable changes to whati8 are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.5.0] - 2026-03-27

### Added
- **Edit Food Sheet** — Edit food settings (nickname, defaults, favorite) directly from Log screen
- **Server-side nutrient summary** — `GET /foods/{id}/summary` endpoint for consistent nutrient/WW calculation
- **NutrientBadges component** — Emoji-based nutrient display (🔥cal 🥩protein 🌾fiber)
- **FoodSummary component** — Auto-fetching nutrient display for food previews

### Fixed
- **Recipe nutrient calculation** — Recipes with mixed USDA/custom ingredients now compute correctly
  - Root cause: Atwater energy variants summed incompletely across ingredient types
  - Fix: Coalesce energy/carbs per ingredient before summing, store only plain Energy (39)

### Changed
- QuickLogSheet and EditLogSheet now use server-side summary instead of client-side calculation

## [0.4.0] - 2026-03-25

### Added
- **Fraction input** — Enter quantities as fractions (1/2, 3/4) with decimal toggle
- **Recipe editing** — Edit recipe ingredients after creation
- **Copy/move logs** — Copy or move food logs between dates
- **Local date handling** — Proper timezone-aware date display

### Fixed
- Portion description display issues
- Data quality improvements across the board
- All test failures resolved (86 tests passing)

## [0.3.0] - 2026-03-02

### Added
- **Hybrid search** — Cohere embeddings with Ollama fallback
- **Cohere Rerank** — Configurable reranking strategies (B + C)
- **Search analytics** — Log search selections for quality tracking
- **Architecture docs** — ARCHITECTURE.md and ROADMAP.md

### Changed
- Rerank config moved from .env to config.toml

### Fixed
- Parameter binding in embed_foods store_embeddings function

## [0.2.0] - 2026-02-10

### Added
- **Timezone-aware timestamps** — Database and frontend properly handle user timezone
- **Food units & weights** — Comprehensive portion/unit system with custom units
- **Custom foods** — Create and manage personal foods not in USDA database
- **Batch summary endpoint** — Nutrition totals after logging multiple foods
- **Comprehensive test suite** — 86 tests covering edge cases

### Fixed
- BCrypt version compatibility (4.3.0 → 4.0.1 for passlib)
- Custom food nutrition calculation
- Portion creation for custom foods
- Food search prioritizes custom foods

## [0.1.0] - 2026-02-08

### Added
- **AI food resolution** — Claude-powered natural language food logging
- **USDA database** — 8,058 foods, 260 nutrients, household portions
- **Food search API** — Trigram similarity search
- **Agent API** — Conversational food logging interface
- **Domain model** — Foods, nutrients, portions, logs, users

---

[Unreleased]: https://github.com/apcooley/whati8/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/apcooley/whati8/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/apcooley/whati8/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/apcooley/whati8/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/apcooley/whati8/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/apcooley/whati8/releases/tag/v0.1.0
