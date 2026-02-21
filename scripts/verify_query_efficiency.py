"""
Verify query efficiency for food log endpoints.

This script tests that we're not hitting N+1 query problems.
"""

import asyncio
import logging

from sqlalchemy import event, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from whati8.database import AsyncSessionLocal
from whati8.models import Food, FoodLog, FoodNutrient

# Track queries
query_count = 0
queries = []


@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, params, context, executemany):
    """Log all SQL queries."""
    global query_count, queries
    query_count += 1
    # Simplify query for display
    query_str = statement.strip().split("\n")[0][:100]
    queries.append(query_str)


async def test_list_food_logs_efficiency(db: AsyncSession, user_id: int):
    """Test the list endpoint query efficiency."""
    global query_count, queries
    query_count = 0
    queries = []

    print("Testing list food logs endpoint query efficiency...")
    print("-" * 60)

    # This mimics what the list endpoint does
    query = (
        select(FoodLog)
        .where(FoodLog.user_id == user_id)
        .options(
            selectinload(FoodLog.food)
            .selectinload(Food.food_nutrients)
            .selectinload(FoodNutrient.nutrient),
            selectinload(FoodLog.meal),
        )
        .order_by(FoodLog.logged_at.desc())
        .limit(10)
    )

    result = await db.execute(query)
    logs = result.scalars().all()

    # Count query
    count_query = select(func.count()).select_from(FoodLog).where(
        FoodLog.user_id == user_id
    )
    await db.scalar(count_query)  # Execute count query to include in metrics

    print(f"Retrieved {len(logs)} logs")
    print(f"Total queries executed: {query_count}")
    print("\nQuery breakdown:")
    for i, q in enumerate(queries, 1):
        print(f"  {i}. {q}...")

    print("\nExpected queries:")
    print("  1. SELECT food_logs with filters")
    print("  2. SELECT foods (joined)")
    print("  3. SELECT food_nutrients (joined)")
    print("  4. SELECT nutrients (joined)")
    print("  5. SELECT meals (joined)")
    print("  6. COUNT query for total")
    print(f"\nResult: {'✓ PASS' if query_count <= 7 else '✗ FAIL'} (used {query_count} queries, expected ≤7)")

    return query_count <= 7


async def test_get_single_log_efficiency(db: AsyncSession, log_id: int):
    """Test the get single log endpoint query efficiency."""
    global query_count, queries
    query_count = 0
    queries = []

    print("\n" + "=" * 60)
    print("Testing get single food log endpoint query efficiency...")
    print("-" * 60)

    # First the ownership check (basic get)
    log = await db.get(FoodLog, log_id)

    # Then reload with relationships
    query = (
        select(FoodLog)
        .options(
            selectinload(FoodLog.food)
            .selectinload(Food.food_nutrients)
            .selectinload(FoodNutrient.nutrient),
            selectinload(FoodLog.meal),
        )
        .where(FoodLog.id == log_id)
    )
    result = await db.execute(query)
    log = result.scalar_one()

    print(f"Retrieved log: {log.id}")
    print(f"Total queries executed: {query_count}")
    print("\nQuery breakdown:")
    for i, q in enumerate(queries, 1):
        print(f"  {i}. {q}...")

    print("\nExpected queries:")
    print("  1. SELECT food_log by ID (ownership check)")
    print("  2. SELECT food_log with filters")
    print("  3. SELECT food")
    print("  4. SELECT food_nutrients")
    print("  5. SELECT nutrients")
    print("  6. SELECT meal")
    print(f"\nResult: {'✓ PASS' if query_count <= 7 else '✗ FAIL'} (used {query_count} queries, expected ≤7)")

    return query_count <= 7


async def main():
    """Run efficiency tests."""
    async with AsyncSessionLocal() as db:
        # Get first user with food logs
        result = await db.execute(
            select(FoodLog.user_id)
            .distinct()
            .limit(1)
        )
        user_id = result.scalar_one_or_none()

        if not user_id:
            print("No food logs found. Please create some food logs first.")
            return

        # Get a log ID for testing
        result = await db.execute(
            select(FoodLog.id)
            .where(FoodLog.user_id == user_id)
            .limit(1)
        )
        log_id = result.scalar_one_or_none()

        if not log_id:
            print("No food logs found for user. Please create some food logs first.")
            return

        print("=" * 60)
        print("FOOD LOG API QUERY EFFICIENCY TEST")
        print("=" * 60)
        print()

        test1 = await test_list_food_logs_efficiency(db, user_id)
        test2 = await test_get_single_log_efficiency(db, log_id)

        print("\n" + "=" * 60)
        if test1 and test2:
            print("✓ ALL EFFICIENCY TESTS PASSED")
            print("No N+1 query problems detected!")
        else:
            print("✗ SOME TESTS FAILED")
            print("There may be N+1 query issues.")
        print("=" * 60)


if __name__ == "__main__":
    # Setup logging to see SQLAlchemy queries
    logging.basicConfig()
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)  # Don't show queries twice

    asyncio.run(main())
