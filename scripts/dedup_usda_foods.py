#!/usr/bin/env python3
"""Deduplicate USDA foods.

Foundation foods (higher usda_fdc_id, typically >= 2000000) are preferred over
SR Legacy foods (lower usda_fdc_id). This script finds duplicates, migrates all
references from the SR Legacy food to the Foundation food, then deletes the
SR Legacy food.

Usage:
    python scripts/dedup_usda_foods.py              # Dry-run (default)
    python scripts/dedup_usda_foods.py --apply      # Actually execute
"""

import argparse
import asyncio
import sys
from collections import defaultdict

from sqlalchemy import select, text, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, "/home/aaron/source/whati8")

from whati8.database import AsyncSessionLocal
from whati8.models import Food


async def find_duplicates(db: AsyncSession) -> dict[str, list[tuple[int, int]]]:
    """Find USDA foods with duplicate names.

    Returns:
        Dict mapping food name to list of (food_id, usda_fdc_id) tuples
    """
    result = await db.execute(text("""
        SELECT id, name, usda_fdc_id
        FROM foods
        WHERE usda_fdc_id IS NOT NULL
          AND is_recipe_expired = false
        ORDER BY name, usda_fdc_id
    """))

    rows = result.fetchall()

    # Group by name
    by_name = defaultdict(list)
    for food_id, name, fdc_id in rows:
        by_name[name].append((food_id, fdc_id))

    # Filter to only those with duplicates
    duplicates = {
        name: foods
        for name, foods in by_name.items()
        if len(foods) > 1
    }

    return duplicates


async def migrate_references(
    db: AsyncSession,
    from_food_id: int,
    to_food_id: int,
    dry_run: bool
) -> dict[str, int]:
    """Migrate all references from one food to another.

    Returns:
        Dict with counts of migrated records per table
    """
    counts = {}

    # user_foods
    result = await db.execute(text("""
        SELECT COUNT(*) FROM user_foods WHERE food_id = :from_id
    """), {"from_id": from_food_id})
    counts["user_foods"] = result.scalar() or 0

    if not dry_run and counts["user_foods"] > 0:
        await db.execute(text("""
            UPDATE user_foods SET food_id = :to_id WHERE food_id = :from_id
        """), {"to_id": to_food_id, "from_id": from_food_id})

    # food_logs
    result = await db.execute(text("""
        SELECT COUNT(*) FROM food_logs WHERE food_id = :from_id
    """), {"from_id": from_food_id})
    counts["food_logs"] = result.scalar() or 0

    if not dry_run and counts["food_logs"] > 0:
        await db.execute(text("""
            UPDATE food_logs SET food_id = :to_id WHERE food_id = :from_id
        """), {"to_id": to_food_id, "from_id": from_food_id})

    # recipe_ingredients
    result = await db.execute(text("""
        SELECT COUNT(*) FROM recipe_ingredients WHERE food_id = :from_id
    """), {"from_id": from_food_id})
    counts["recipe_ingredients"] = result.scalar() or 0

    if not dry_run and counts["recipe_ingredients"] > 0:
        await db.execute(text("""
            UPDATE recipe_ingredients SET food_id = :to_id WHERE food_id = :from_id
        """), {"to_id": to_food_id, "from_id": from_food_id})

    # food_nutrients (delete instead of migrate to avoid duplicates)
    result = await db.execute(text("""
        SELECT COUNT(*) FROM food_nutrients WHERE food_id = :from_id
    """), {"from_id": from_food_id})
    counts["food_nutrients"] = result.scalar() or 0

    if not dry_run and counts["food_nutrients"] > 0:
        await db.execute(text("""
            DELETE FROM food_nutrients WHERE food_id = :from_id
        """), {"from_id": from_food_id})

    return counts


async def main(dry_run: bool = True):
    """Find and deduplicate USDA foods."""
    async with AsyncSessionLocal() as db:
        duplicates = await find_duplicates(db)

        if not duplicates:
            print("✅ No duplicate USDA foods found!")
            return 0

        print(f"Found {len(duplicates)} food names with duplicates\n")

        total_deleted = 0
        for name, foods in sorted(duplicates.items()):
            # Sort by fdc_id descending - highest (Foundation) first
            foods_sorted = sorted(foods, key=lambda x: x[1], reverse=True)

            # Keep the Foundation food (highest fdc_id)
            keep_id, keep_fdc = foods_sorted[0]
            delete_foods = foods_sorted[1:]

            print(f"📦 {name}")
            print(f"   KEEP: id={keep_id}, fdc_id={keep_fdc} (Foundation)")

            for del_id, del_fdc in delete_foods:
                print(f"   DELETE: id={del_id}, fdc_id={del_fdc} (SR Legacy)")

                # Migrate references
                counts = await migrate_references(db, del_id, keep_id, dry_run)

                if any(counts.values()):
                    print(f"      → Migrate: {dict(counts)}")

                # Delete the SR Legacy food
                if not dry_run:
                    await db.execute(text("""
                        DELETE FROM foods WHERE id = :id
                    """), {"id": del_id})

                total_deleted += 1

            print()

        if dry_run:
            print(f"🔍 DRY RUN: Would delete {total_deleted} SR Legacy foods")
            print("   Run with --apply to execute changes")
        else:
            await db.commit()
            print(f"✅ Deleted {total_deleted} SR Legacy foods and migrated references")

        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deduplicate USDA foods")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually execute changes (default is dry-run)"
    )
    args = parser.parse_args()

    sys.exit(asyncio.run(main(dry_run=not args.apply)))
