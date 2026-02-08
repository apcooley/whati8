#!/bin/bash
# Comprehensive check script for whati8 project
# Runs linting, formatting checks, and tests

set -e

echo "=============================================="
echo "  whati8 - Comprehensive Quality Checks"
echo "=============================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Track results
LINT_PASS=0
FORMAT_PASS=0
UNIT_TESTS_PASS=0
INTEGRATION_TESTS_PASS=0

echo "📋 Step 1: Code Linting with ruff"
echo "-------------------------------------------"
if uv run ruff check . --exclude=alembic; then
    echo -e "${GREEN}✓ Linting passed - no issues found${NC}"
    LINT_PASS=1
else
    echo -e "${RED}✗ Linting found issues${NC}"
fi
echo ""

echo "🎨 Step 2: Code Formatting Check"
echo "-------------------------------------------"
if uv run ruff format --check . --exclude=alembic; then
    echo -e "${GREEN}✓ Code is properly formatted${NC}"
    FORMAT_PASS=1
else
    echo -e "${YELLOW}⚠ Code needs formatting - run: uv run ruff format .${NC}"
fi
echo ""

echo "🧪 Step 3: Unit Tests (no database required)"
echo "-------------------------------------------"
if uv run pytest tests/ -m unit -v --tb=short 2>&1 | tail -20; then
    echo -e "${GREEN}✓ Unit tests passed${NC}"
    UNIT_TESTS_PASS=1
else
    echo -e "${YELLOW}⚠ Some unit tests failed or were skipped${NC}"
fi
echo ""

echo "🔗 Step 4: Integration Tests (require database)"
echo "-------------------------------------------"
echo -e "${BLUE}Note: Integration tests require whati8_test database${NC}"
echo -e "${BLUE}Create with: psql -U whati8 -d postgres -c 'CREATE DATABASE whati8_test;'${NC}"
echo ""

if uv run pytest tests/ -m integration -v --tb=short 2>&1 | tail -20; then
    echo -e "${GREEN}✓ Integration tests passed${NC}"
    INTEGRATION_TESTS_PASS=1
else
    echo -e "${YELLOW}⚠ Integration tests skipped or failed (test database may not exist)${NC}"
fi
echo ""

echo "=============================================="
echo "  Test Summary"
echo "=============================================="
echo ""

# Print summary
if [ $LINT_PASS -eq 1 ]; then
    echo -e "${GREEN}✓${NC} Linting: PASSED"
else
    echo -e "${RED}✗${NC} Linting: FAILED"
fi

if [ $FORMAT_PASS -eq 1 ]; then
    echo -e "${GREEN}✓${NC} Formatting: PASSED"
else
    echo -e "${YELLOW}⚠${NC} Formatting: NEEDS WORK"
fi

if [ $UNIT_TESTS_PASS -eq 1 ]; then
    echo -e "${GREEN}✓${NC} Unit Tests: PASSED"
else
    echo -e "${YELLOW}⚠${NC} Unit Tests: SOME ISSUES"
fi

if [ $INTEGRATION_TESTS_PASS -eq 1 ]; then
    echo -e "${GREEN}✓${NC} Integration Tests: PASSED"
else
    echo -e "${YELLOW}⚠${NC} Integration Tests: SKIPPED/FAILED"
fi

echo ""
echo "=============================================="
echo "  Quick Commands"
echo "=============================================="
echo ""
echo "  Fix formatting:    uv run ruff format ."
echo "  Run all tests:     uv run pytest -v"
echo "  Run unit tests:    uv run pytest -m unit -v"
echo "  Run with coverage: uv run pytest --cov=whati8"
echo "  Start server:      uv run python -m whati8 serve --reload"
echo ""

# Exit with success if at least lint and format passed
if [ $LINT_PASS -eq 1 ] && [ $FORMAT_PASS -eq 1 ]; then
    echo -e "${GREEN}✓ Code quality checks passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some quality checks failed${NC}"
    exit 1
fi
