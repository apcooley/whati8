from decimal import Decimal
#!/usr/bin/env python3
"""Migrate Energy nutrient from kJ to kcal.

This script performs the following steps:
1. Change nutrient 39 (Energy) unit from 'kJ' to 'kcal'
2. USDA foods: Values will be fixed by re-import (not handled here)
3. Custom foods (created_by_user_id IS NOT NULL):
   - Their values were stored as kcal*4.184 (converted to kJ)
   - Need to divide by 4.184 to get back to kcal

Usage:
    uv run python scripts/migrate_energy_to_kcal.py

IMPORTANT: Run this BEFORE re-importing USDA foods.
After this script:
- Custom food calories will be correct in kcal
- USDA food calories will be wrong (still in kJ but unit says kcal)
- Re-import USDA foods to fix their values
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from whati8.database import AsyncSessionLocal
from whati8.models import Nutrient, Food, FoodNutrient


async def migrate():
    """Perform the migration."""
    async with AsyncSessionLocal() as db:
        # Step 1: Update Energy nutrient unit from kJ to kcal
        print("Step 1: Updating Energy nutrient unit from kJ to kcal...")
        result = await db.execute(
            select(Nutrient).where(Nutrient.id == 39)
        )
        energy_nutrient = result.scalar_one_or_none()
        
        if not energy_nutrient:
            print("ERROR: Energy nutrient (id=39) not found!")
            return False
        
        if energy_nutrient.unit != "kJ":
            print(f"Energy nutrient already '{energy_nutrient.unit}' — skipping unit change.")
        
        energy_nutrient.unit = "kcal"
        await db.commit()
        print("✓ Changed Energy nutrient unit: kJ → kcal")
        
        # Step 2: Convert custom food energy values from kJ back to kcal
        print("\nStep 2: Converting custom food energy values...")
        
        # Find all custom foods (those with created_by_user_id set)
        result = await db.execute(
            select(Food).where(Food.created_by_user_id.isnot(None))
        )
        custom_foods = result.scalars().all()
        print(f"Found {len(custom_foods)} custom foods")
        
        # For each custom food, find its Energy nutrient and divide by 4.184
        updated_count = 0
        for food in custom_foods:
            result = await db.execute(
                select(FoodNutrient)
                .where(
                    FoodNutrient.food_id == food.id,
                    FoodNutrient.nutrient_id == 39  # Energy
                )
            )
            energy_fn = result.scalar_one_or_none()
            
            if energy_fn:
                old_value = energy_fn.amount_per_serving
                new_value = old_value / Decimal("4.184")
                energy_fn.amount_per_serving = new_value
                updated_count += 1
                print(f"  Food '{food.name}': {old_value:.2f} kJ → {new_value:.2f} kcal")
        
        await db.commit()
        print(f"✓ Updated {updated_count} custom food energy values")
        
        # Step 3: Warn about USDA foods
        result = await db.execute(
            select(Food).where(Food.created_by_user_id.is_(None))
        )
        usda_count = len(result.scalars().all())
        
        print(f"\n⚠️  WARNING: {usda_count} USDA foods still have kJ values!")
        print("   These will show incorrect calorie counts until you re-import USDA data.")
        print("   The import script will handle the conversion automatically.")
        
        return True


async def main():
    """Main entry point."""
    print("=" * 60)
    print("Energy Nutrient Migration: kJ → kcal")
    print("=" * 60)
    print()
    
    success = await migrate()
    
    print()
    print("=" * 60)
    if success:
        print("✓ Migration completed successfully!")
        print()
        print("Next steps:")
        print("1. Re-import USDA foods to convert their values")
        print("2. Restart the API server")
        print("3. Run tests to verify: uv run pytest tests/test_kcal_migration.py")
    else:
        print("✗ Migration failed or was already run")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
