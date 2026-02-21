# whati8 Test Suite

Comprehensive test suite for the whati8 nutrition tracker.

## Test Structure

```
tests/
├── conftest.py          # Pytest fixtures and configuration
├── test_auth.py         # Authentication tests (service + API)
├── test_food_api.py     # Food search and details API tests
├── test_food_resolver.py # AI food resolution tests (mocked)
├── test_models.py       # Database model tests
└── README.md            # This file
```

## Test Categories

Tests are marked with categories for selective running:

- `@pytest.mark.unit` - Unit tests (no external dependencies)
- `@pytest.mark.integration` - Integration tests (require database)
- `@pytest.mark.api` - API endpoint tests
- `@pytest.mark.auth` - Authentication tests
- `@pytest.mark.db` - Database model tests
- `@pytest.mark.ai` - AI service tests (mocked, no API key needed)

## Prerequisites

### 1. Install Test Dependencies

```bash
uv sync  # Installs all dependencies including dev dependencies
```

### 2. Create Test Database

The test suite uses a separate `whati8_test` database to avoid affecting development data.

**Option A: Using existing database connection**
```bash
# Connect to your PostgreSQL instance
psql -U whati8 -d postgres -c "CREATE DATABASE whati8_test;"
```

**Option B: Using the setup script** (if you have a postgres superuser)
```bash
# As postgres user
sudo -u postgres psql -c "CREATE DATABASE whati8_test OWNER whati8;"
```

**Option C: Manual SQL**
```sql
-- Connect to postgres database
\c postgres

-- Create test database
CREATE DATABASE whati8_test;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE whati8_test TO whati8;
```

### 3. Environment Configuration

Tests use the same `.env` file as the main application but replace the database name with `whati8_test`.

Ensure your `.env` has:
```bash
DATABASE_URL=postgresql://whati8:your_password@localhost:5432/whati8
ANTHROPIC_API_KEY=sk-ant-...  # Only needed for non-mocked AI tests
JWT_SECRET=your_jwt_secret_min_32_chars
USDA_API_KEY=your_usda_key
```

## Running Tests

### Run All Tests
```bash
uv run pytest
```

### Run Specific Test Categories
```bash
# Unit tests only (fast, no database needed)
uv run pytest -m unit

# Integration tests (require database)
uv run pytest -m integration

# API tests
uv run pytest -m api

# Authentication tests
uv run pytest -m auth

# AI tests (mocked, fast)
uv run pytest -m ai
```

### Run Specific Test Files
```bash
# Authentication tests
uv run pytest tests/test_auth.py -v

# Food API tests
uv run pytest tests/test_food_api.py -v

# AI food resolver tests
uv run pytest tests/test_food_resolver.py -v

# Database model tests
uv run pytest tests/test_models.py -v
```

### Run Specific Test Classes or Functions
```bash
# Run a specific test class
uv run pytest tests/test_auth.py::TestAuthService -v

# Run a specific test function
uv run pytest tests/test_auth.py::TestAuthService::test_create_user -v
```

### Run with Coverage
```bash
# Install coverage
uv add --dev pytest-cov

# Run with coverage report
uv run pytest --cov=whati8 --cov-report=html --cov-report=term

# View HTML report
open htmlcov/index.html
```

### Run with Verbose Output
```bash
# Show all test names and results
uv run pytest -v

# Show print statements
uv run pytest -s

# Show local variables on failures
uv run pytest -l

# Stop on first failure
uv run pytest -x
```

## Test Fixtures

Key fixtures available in `conftest.py`:

- `db_session` - Clean database session for each test
- `test_engine` - Async database engine
- `seed_test_data` - Populate database with test data (nutrients, meals, sample food)
- `test_user` - Create a test user
- `test_user_token` - JWT token for test user
- `client` - Async HTTP client for API testing
- `authenticated_client` - HTTP client with authentication headers

## Writing New Tests

### Example: Unit Test
```python
@pytest.mark.unit
class TestMyService:
    async def test_something(self):
        result = MyService.do_something()
        assert result == expected
```

### Example: Integration Test with Database
```python
@pytest.mark.integration
@pytest.mark.db
class TestMyModel:
    async def test_create(self, db_session: AsyncSession, seed_test_data):
        obj = MyModel(name="test")
        db_session.add(obj)
        await db_session.commit()
        assert obj.id is not None
```

### Example: API Test
```python
@pytest.mark.api
@pytest.mark.integration
class TestMyEndpoint:
    async def test_endpoint(self, authenticated_client: AsyncClient):
        response = await authenticated_client.get("/my-endpoint")
        assert response.status_code == 200
```

### Example: Mocked AI Test
```python
from unittest.mock import patch, MagicMock

@pytest.mark.ai
@pytest.mark.unit
class TestAIService:
    @patch("mymodule.Anthropic")
    async def test_parse(self, mock_anthropic_class):
        # Setup mock
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        # ... configure mock response

        # Test
        result = await MyService.call_ai()
        assert result is not None
```

## Troubleshooting

### Test Database Connection Issues

**Error:** `password authentication failed for user "whati8_test"`
- **Cause:** Test database doesn't exist or wrong permissions
- **Fix:** Create the test database (see Prerequisites)

**Error:** `database "whati8_test" does not exist`
- **Cause:** Test database not created
- **Fix:** Run `psql -U whati8 -d postgres -c "CREATE DATABASE whati8_test;"`

### Import Errors

**Error:** `cannot import name 'X' from 'whati8.Y'`
- **Cause:** Missing dependency or incorrect import path
- **Fix:** Run `uv sync` to install all dependencies

### Test Isolation Issues

**Problem:** Tests pass individually but fail when run together
- **Cause:** Shared state between tests
- **Fix:** Ensure each test uses fixtures and doesn't modify global state

### Slow Tests

**Problem:** Tests take too long
- **Solution:** Run only unit tests: `pytest -m unit`
- **Solution:** Run tests in parallel: `pytest -n auto` (requires pytest-xdist)

## Continuous Integration

For CI/CD pipelines:

```bash
# Install dependencies
uv sync

# Lint code
uv run ruff check .
uv run ruff format --check .

# Run tests (assuming test database exists)
uv run pytest -v --tb=short

# Run with coverage
uv run pytest --cov=whati8 --cov-report=xml --cov-report=term
```

## Test Coverage Goals

- **Unit Tests:** 80%+ coverage of service layer and schemas
- **Integration Tests:** All API endpoints tested
- **Database Tests:** All models and relationships tested
- **AI Tests:** All AI service methods tested (with mocks)

## Future Enhancements

- [ ] Add pytest-xdist for parallel test execution
- [ ] Add mutation testing with mutmut
- [ ] Add property-based testing with Hypothesis
- [ ] Add load testing for API endpoints
- [ ] Add end-to-end tests with Playwright
- [ ] Add test data factories with Factory Boy
- [ ] Add snapshot testing for API responses
