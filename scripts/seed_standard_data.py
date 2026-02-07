#!/usr/bin/env python3
"""
Seed standard nutrients and meals into the database.

Run this after creating the database schema to populate:
- Standard nutrients (calories, protein, carbs, fat, etc.)
- Standard meals (breakfast, lunch, dinner, snack)
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from whati8.database import AsyncSessionLocal
from whati8.models import Meal, Nutrient


async def seed_nutrients():
    """Create standard nutrients."""
    async with AsyncSessionLocal() as session:
        # Check if nutrients already exist
        from sqlalchemy import select

        result = await session.execute(select(Nutrient).limit(1))
        if result.scalar_one_or_none():
            print("  ⚠ Nutrients already exist, skipping...")
            return

        standard_nutrients = [
            # Macronutrients
            Nutrient(
                name="Calories",
                unit="kcal",
                description="Energy content",
                created_by_user_id=None,
            ),
            Nutrient(
                name="Protein",
                unit="g",
                description="Protein content",
                created_by_user_id=None,
            ),
            Nutrient(
                name="Total Carbohydrates",
                unit="g",
                description="Total carbohydrate content",
                created_by_user_id=None,
            ),
            Nutrient(
                name="Total Fat",
                unit="g",
                description="Total fat content",
                created_by_user_id=None,
            ),
            # Fiber and Sugar
            Nutrient(
                name="Dietary Fiber",
                unit="g",
                description="Dietary fiber content",
                created_by_user_id=None,
            ),
            Nutrient(
                name="Total Sugars",
                unit="g",
                description="Total sugar content",
                created_by_user_id=None,
            ),
            # Fat breakdown
            Nutrient(
                name="Saturated Fat",
                unit="g",
                description="Saturated fat content",
                created_by_user_id=None,
            ),
            Nutrient(
                name="Trans Fat",
                unit="g",
                description="Trans fat content",
                created_by_user_id=None,
            ),
            Nutrient(
                name="Monounsaturated Fat",
                unit="g",
                description="Monounsaturated fat content",
                created_by_user_id=None,
            ),
            Nutrient(
                name="Polyunsaturated Fat",
                unit="g",
                description="Polyunsaturated fat content",
                created_by_user_id=None,
            ),
            # Micronutrients
            Nutrient(
                name="Sodium",
                unit="mg",
                description="Sodium content",
                created_by_user_id=None,
            ),
            Nutrient(
                name="Cholesterol",
                unit="mg",
                description="Cholesterol content",
                created_by_user_id=None,
            ),
            Nutrient(
                name="Potassium",
                unit="mg",
                description="Potassium content",
                created_by_user_id=None,
            ),
            # Vitamins
            Nutrient(
                name="Vitamin A",
                unit="mcg",
                description="Vitamin A content",
                created_by_user_id=None,
            ),
            Nutrient(
                name="Vitamin C",
                unit="mg",
                description="Vitamin C content",
                created_by_user_id=None,
            ),
            Nutrient(
                name="Vitamin D",
                unit="mcg",
                description="Vitamin D content",
                created_by_user_id=None,
            ),
            Nutrient(
                name="Calcium",
                unit="mg",
                description="Calcium content",
                created_by_user_id=None,
            ),
            Nutrient(
                name="Iron",
                unit="mg",
                description="Iron content",
                created_by_user_id=None,
            ),
        ]

        session.add_all(standard_nutrients)
        await session.commit()
        print(f"  ✓ Created {len(standard_nutrients)} standard nutrients")


async def seed_meals():
    """Create standard meals."""
    async with AsyncSessionLocal() as session:
        # Check if meals already exist
        from sqlalchemy import select

        result = await session.execute(select(Meal).limit(1))
        if result.scalar_one_or_none():
            print("  ⚠ Meals already exist, skipping...")
            return

        standard_meals = [
            Meal(
                name="Breakfast",
                created_by_user_id=None,
                display_order=1,
            ),
            Meal(
                name="Lunch",
                created_by_user_id=None,
                display_order=2,
            ),
            Meal(
                name="Dinner",
                created_by_user_id=None,
                display_order=3,
            ),
            Meal(
                name="Snack",
                created_by_user_id=None,
                display_order=4,
            ),
        ]

        session.add_all(standard_meals)
        await session.commit()
        print(f"  ✓ Created {len(standard_meals)} standard meals")


async def main():
    """Run all seed operations."""
    print("=" * 60)
    print("Seeding Standard Data")
    print("=" * 60)

    print("\nCreating standard nutrients...")
    try:
        await seed_nutrients()
    except Exception as e:
        print(f"  ✗ Error seeding nutrients: {e}")
        return 1

    print("\nCreating standard meals...")
    try:
        await seed_meals()
    except Exception as e:
        print(f"  ✗ Error seeding meals: {e}")
        return 1

    print("\n" + "=" * 60)
    print("✓ Seeding complete!")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
