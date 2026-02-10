"""Pytest fixtures and configuration for whati8 tests."""

import asyncio
from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from whati8.api.app import create_app
from whati8.config import settings
from whati8.models import Food, Meal, Nutrient, User
from whati8.models.base import Base
from whati8.services.auth import AuthService


# Test database URL (use a separate test database)
# Only replace the database name at the end, not the username
_base_url = str(settings.database_url)
if _base_url.endswith("/whati8"):
    TEST_DATABASE_URL = _base_url[:-7] + "/whati8_test"
else:
    # Fallback: replace last occurrence only
    TEST_DATABASE_URL = "/whati8_test".join(_base_url.rsplit("/whati8", 1))
# Ensure using asyncpg driver
if not TEST_DATABASE_URL.startswith("postgresql+asyncpg://"):
    TEST_DATABASE_URL = TEST_DATABASE_URL.replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )


@pytest.fixture(scope="module")
def event_loop():
    """Create event loop for async tests (per module)."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def test_engine():
    """Create test database engine (per module)."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,  # Disable pooling for tests
    )
    yield engine
    await engine.dispose()


@pytest.fixture(scope="module")
async def setup_database(test_engine):
    """Create all tables in test database (per module).
    
    Creates tables once per test module and drops them after.
    This ensures each test file starts with clean tables.
    """
    from sqlalchemy import text
    
    try:
        # Create pg_trgm extension (required for fuzzy search)
        async with test_engine.connect() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            await conn.commit()
        
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        yield
        # Don't drop tables at end - next module will drop/recreate anyway
    except Exception as e:
        pytest.skip(f"Test database not available: {e}")


@pytest.fixture
async def db_session(test_engine, setup_database) -> AsyncGenerator[AsyncSession, None]:
    """Create a clean database session for each test.
    
    Uses connection-level transaction that gets rolled back, ensuring test isolation
    even when test code calls commit().
    """
    async with test_engine.connect() as conn:
        # Start a transaction that we'll roll back at the end
        trans = await conn.begin()
        
        # Create session bound to this connection
        AsyncTestingSessionLocal = sessionmaker(
            bind=conn,
            class_=AsyncSession,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",  # commits become savepoints
        )
        
        async with AsyncTestingSessionLocal() as session:
            yield session
        
        # Rollback the outer transaction - undoes everything including "commits"
        await trans.rollback()


@pytest.fixture
async def seed_test_data(db_session: AsyncSession):
    """Seed minimal test data (nutrients, meals, sample food)."""
    # Create standard nutrients
    nutrients_data = [
        {"name": "Energy", "unit": "kcal", "description": "Calories"},
        {"name": "Protein", "unit": "g", "description": "Protein"},
        {"name": "Carbohydrate, by difference", "unit": "g", "description": "Carbs"},
        {"name": "Total lipid (fat)", "unit": "g", "description": "Fat"},
        {"name": "Fiber, total dietary", "unit": "g", "description": "Dietary fiber"},
    ]

    for nutrient_data in nutrients_data:
        nutrient = Nutrient(**nutrient_data)
        db_session.add(nutrient)

    # Create standard meals (no description field in current model)
    meals_data = [
        {"name": "Breakfast"},
        {"name": "Lunch"},
        {"name": "Dinner"},
        {"name": "Snack"},
    ]

    for meal_data in meals_data:
        meal = Meal(**meal_data)
        db_session.add(meal)

    # Create sample food
    sample_food = Food(
        name="Egg, whole, raw",
        brand=None,
        serving_size=50.0,
        unit="g",
        usda_fdc_id=123456,
    )
    db_session.add(sample_food)

    await db_session.commit()
    await db_session.refresh(sample_food)

    # Add food nutrients
    from whati8.models import FoodNutrient

    energy_nutrient = await db_session.scalar(
        select(Nutrient).where(Nutrient.name == "Energy")
    )
    protein_nutrient = await db_session.scalar(
        select(Nutrient).where(Nutrient.name == "Protein")
    )

    if energy_nutrient:
        fn1 = FoodNutrient(
            food_id=sample_food.id,
            nutrient_id=energy_nutrient.id,
            amount_per_serving=72.0,
        )
        db_session.add(fn1)

    if protein_nutrient:
        fn2 = FoodNutrient(
            food_id=sample_food.id,
            nutrient_id=protein_nutrient.id,
            amount_per_serving=6.3,
        )
        db_session.add(fn2)

    await db_session.commit()

    yield

    # Cleanup is handled by session rollback


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    from whati8.schemas.auth import UserCreate

    user_data = UserCreate(
        username="testuser",
        email="test@example.com",
        password="testpassword123",
    )

    user = await AuthService.create_user(db_session, user_data)
    return user


@pytest.fixture
async def test_user_token(test_user: User) -> str:
    """Generate JWT token for test user."""
    token = AuthService.create_access_token(user_id=test_user.id)
    return token


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for API testing."""
    app = create_app()

    # Override get_db dependency to use test database
    from whati8.api.deps import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
async def authenticated_client(
    client: AsyncClient, test_user_token: str
) -> AsyncClient:
    """Create authenticated HTTP client with JWT token."""
    client.headers["Authorization"] = f"Bearer {test_user_token}"
    return client
