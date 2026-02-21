#!/usr/bin/env python3
"""
Import USDA Food Data Central bulk data into the database.

Downloads bulk JSON files from USDA FDC and imports foods with nutrients.
Focuses on Foundation Foods and SR Legacy for core nutrition data.

Usage:
    uv run python scripts/import_usda_data.py [--limit N]
    uv run python -m whati8 import-usda [--limit N]

Resources:
- Bulk downloads: https://fdc.nal.usda.gov/download-datasets/
- API guide: https://fdc.nal.usda.gov/api-guide/
- Nutrient documentation: https://www.nal.usda.gov/human-nutrition-and-food-safety/nutrient-lists-standard-reference-legacy-2018
"""

import asyncio
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from whati8.database import AsyncSessionLocal  # noqa: E402
from whati8.models import Food, FoodNutrient, FoodPortion, Nutrient  # noqa: E402


# Bulk download URLs (updated periodically by USDA)
DOWNLOAD_URLS = {
    "foundation": "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_foundation_food_json_2023-10-26.zip",
    "sr_legacy": "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_json_2021-10-28.zip",
}


class USDAImporter:
    """Import USDA Food Data Central bulk data."""

    def __init__(self, limit: int | None = None):
        self.limit = limit
        self.download_dir = project_root / "data" / "usda"
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.nutrient_id_map: dict[int, int] = {}  # USDA nutrient ID -> our DB nutrient ID
        self.nutrient_name_map: dict[str, int] = {}  # USDA nutrient name -> our DB nutrient ID
        self.db = None
        self.stats = {
            "foods_created": 0,
            "foods_skipped": 0,
            "nutrients_linked": 0,
            "portions_created": 0,
            "nutrients_created": 0,
        }

    async def load_nutrient_mapping(self):
        """Load and create nutrient mappings from database."""
        print("Loading nutrient mappings from database...")
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Nutrient).where(Nutrient.created_by_user_id.is_(None))
            )
            nutrients = result.scalars().all()

            self.nutrient_name_map = {n.name: n.id for n in nutrients}
            print(f"  ✓ Loaded {len(self.nutrient_name_map)} standard nutrients")

    def download_file(self, dataset_type: str) -> Path:
        """Download USDA bulk data file if not already cached."""
        url = DOWNLOAD_URLS[dataset_type]
        filename = Path(url).name
        filepath = self.download_dir / filename

        if filepath.exists():
            print(f"  ✓ Using cached file: {filename}")
            return filepath

        print(f"  Downloading {filename}...")
        print(f"    URL: {url}")
        print("    Size: ~50-100 MB, may take 1-2 minutes...")

        with httpx.Client(timeout=300.0) as client:
            response = client.get(url, follow_redirects=True)
            response.raise_for_status()

            with open(filepath, "wb") as f:
                f.write(response.content)

        print(f"  ✓ Downloaded: {filepath}")
        return filepath

    def extract_json(self, zip_path: Path) -> Path:
        """Extract JSON file from ZIP archive."""
        json_dir = self.download_dir / zip_path.stem
        json_file = json_dir / "FoodData_Central_foundation_food_json_2023-10-26.json"

        # Try to find any .json file in the directory
        if json_dir.exists():
            json_files = list(json_dir.glob("*.json"))
            if json_files:
                print(f"  ✓ Using cached JSON: {json_files[0].name}")
                return json_files[0]

        print(f"  Extracting JSON from {zip_path.name}...")
        json_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(json_dir)

        # Find the extracted JSON file
        json_files = list(json_dir.glob("*.json"))
        if not json_files:
            raise FileNotFoundError(f"No JSON file found in {json_dir}")

        json_file = json_files[0]
        print(f"  ✓ Extracted: {json_file.name}")
        return json_file

    async def parse_food_item(
        self, food_data: dict[str, Any], db
    ) -> tuple[Food, list[FoodNutrient], list[FoodPortion]]:
        """Parse USDA food JSON into Food, FoodNutrient, and FoodPortion objects."""
        # Extract food details
        fdc_id = food_data.get("fdcId")
        description = food_data.get("description", "Unknown")

        # Get food category
        category = None
        food_category = food_data.get("foodCategory")
        if food_category:
            category = food_category.get("description")

        # Get serving size info (default to 100g)
        serving_size = 100.0
        unit = "g"

        # Some foods have serving size info in foodPortions
        food_portions_data = food_data.get("foodPortions", [])
        if food_portions_data:
            portion = food_portions_data[0]  # Use first portion
            gram_weight = portion.get("gramWeight", 100.0)
            if gram_weight > 0:
                serving_size = gram_weight
                # Try to get unit from measure unit
                measure_unit = portion.get("measureUnit", {})
                unit_name = measure_unit.get("name", "")
                if unit_name:
                    unit = unit_name

        # Create food object
        food = Food(
            name=description,
            brand=None,  # USDA foods don't have brands
            serving_size=serving_size,
            unit=unit,
            usda_fdc_id=fdc_id,
            category=category,
            created_by_user_id=None,  # NULL for USDA foods
            notes=f"USDA FDC ID: {fdc_id}",
        )

        # Parse nutrients (ALL of them, not just NUTRIENT_MAPPING)
        food_nutrients = []
        nutrients_data = food_data.get("foodNutrients", [])

        for nutrient_data in nutrients_data:
            nutrient_info = nutrient_data.get("nutrient", {})
            usda_nutrient_id = nutrient_info.get("id")
            usda_nutrient_name = nutrient_info.get("name", "Unknown")
            usda_nutrient_unit = nutrient_info.get("unitName", "")
            amount = nutrient_data.get("amount")

            # Skip if no amount or nutrient ID
            if amount is None or usda_nutrient_id is None:
                continue

            # Try to find or create nutrient in database
            our_nutrient_id = None

            # First check if we've already mapped this USDA ID
            if usda_nutrient_id in self.nutrient_id_map:
                our_nutrient_id = self.nutrient_id_map[usda_nutrient_id]
            # Then check by name
            elif usda_nutrient_name in self.nutrient_name_map:
                our_nutrient_id = self.nutrient_name_map[usda_nutrient_name]
                self.nutrient_id_map[usda_nutrient_id] = our_nutrient_id
            else:
                # Create a new nutrient in database
                new_nutrient = Nutrient(
                    name=usda_nutrient_name,
                    unit=usda_nutrient_unit,
                    created_by_user_id=None,  # Standard nutrients
                )
                db.add(new_nutrient)
                await db.flush()  # Get the ID
                our_nutrient_id = new_nutrient.id
                self.nutrient_name_map[usda_nutrient_name] = our_nutrient_id
                self.nutrient_id_map[usda_nutrient_id] = our_nutrient_id
                self.stats["nutrients_created"] += 1

            # Create food nutrient link
            # Skip if we already have this nutrient for this food
            if our_nutrient_id:
                # Check if this nutrient is already in our list
                if not any(fn.nutrient_id == our_nutrient_id for fn in food_nutrients):
                    food_nutrient = FoodNutrient(
                        nutrient_id=our_nutrient_id,
                        amount_per_serving=float(amount),
                    )
                    food_nutrients.append(food_nutrient)
                    self.stats["nutrients_linked"] += 1

        # Parse food portions
        portions = []
        for i, portion_data in enumerate(food_portions_data):
            measure_unit = portion_data.get("measureUnit", {})
            unit_name = measure_unit.get("name", "unit")
            unit_abbreviation = measure_unit.get("abbreviation")
            amount = portion_data.get("amount", portion_data.get("value", 1.0))
            gram_weight = portion_data.get("gramWeight", 100.0)
            modifier = portion_data.get("modifier") or None
            sequence_number = portion_data.get("sequenceNumber", i)

            # Build portion description
            portion_description = f"{amount} {unit_name}"
            if modifier:
                portion_description += f" {modifier}"
            portion_description += f" ({gram_weight}g)"

            portion = FoodPortion(
                amount=float(amount),
                unit_name=unit_name,
                unit_abbreviation=unit_abbreviation,
                gram_weight=float(gram_weight),
                modifier=modifier,
                portion_description=portion_description,
                sequence_number=sequence_number,
            )
            portions.append(portion)
            self.stats["portions_created"] += 1

        return food, food_nutrients, portions

    async def import_foods(self, json_path: Path, dataset_name: str):
        """Import foods from JSON file into database."""
        print(f"\nImporting {dataset_name} foods from {json_path.name}...")

        # Load JSON data
        print("  Loading JSON data...")
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        foods_data = data.get("FoundationFoods", []) or data.get("SRLegacyFoods", [])
        total_foods = len(foods_data)

        if self.limit:
            foods_data = foods_data[: self.limit]
            print(
                f"  ⚠ Limiting import to {self.limit} foods (total available: {total_foods})"
            )
        else:
            print(f"  Found {total_foods} foods to import")

        # Import in batches
        batch_size = 100
        async with AsyncSessionLocal() as db:
            for i in range(0, len(foods_data), batch_size):
                batch = foods_data[i : i + batch_size]
                batch_num = i // batch_size + 1
                total_batches = (len(foods_data) + batch_size - 1) // batch_size

                print(
                    f"  Processing batch {batch_num}/{total_batches}...",
                    end="",
                    flush=True,
                )

                for food_data in batch:
                    try:
                        fdc_id = food_data.get("fdcId")

                        # Check if already exists
                        existing = await db.scalar(
                            select(Food).where(Food.usda_fdc_id == fdc_id)
                        )
                        if existing:
                            self.stats["foods_skipped"] += 1
                            continue

                        # Parse and create food
                        food, food_nutrients, portions = await self.parse_food_item(food_data, db)
                        db.add(food)
                        await db.flush()  # Get food.id

                        # Link nutrients
                        for fn in food_nutrients:
                            fn.food_id = food.id
                            db.add(fn)

                        # Add portions
                        for portion in portions:
                            portion.food_id = food.id
                            db.add(portion)

                        self.stats["foods_created"] += 1

                    except Exception as e:
                        print(
                            f"\n  ✗ Error processing food {food_data.get('fdcId')}: {e}"
                        )
                        import traceback
                        traceback.print_exc()
                        continue

                # Commit batch
                await db.commit()
                print(
                    f" ✓ ({self.stats['foods_created']} created, {self.stats['foods_skipped']} skipped)"
                )

    async def run(self):
        """Run the full import process."""
        print("=" * 70)
        print("USDA Food Data Central Import")
        print("=" * 70)

        # Load nutrient mappings
        await self.load_nutrient_mapping()

        # Import Foundation Foods
        print("\n" + "=" * 70)
        print("1. Foundation Foods (~1,000 core foods)")
        print("=" * 70)
        try:
            zip_path = self.download_file("foundation")
            json_path = self.extract_json(zip_path)
            await self.import_foods(json_path, "Foundation Foods")
        except Exception as e:
            print(f"  ✗ Error importing Foundation Foods: {e}")

        # Import SR Legacy
        print("\n" + "=" * 70)
        print("2. SR Legacy (~8,000 legacy USDA foods)")
        print("=" * 70)
        try:
            zip_path = self.download_file("sr_legacy")
            json_path = self.extract_json(zip_path)
            await self.import_foods(json_path, "SR Legacy")
        except Exception as e:
            print(f"  ✗ Error importing SR Legacy: {e}")

        # Print summary
        print("\n" + "=" * 70)
        print("Import Complete!")
        print("=" * 70)
        print(f"  Foods created:     {self.stats['foods_created']:,}")
        print(f"  Foods skipped:     {self.stats['foods_skipped']:,}")
        print(f"  Nutrients linked:  {self.stats['nutrients_linked']:,}")
        print(f"  Portions created:  {self.stats['portions_created']:,}")
        print(f"  Nutrients created: {self.stats['nutrients_created']:,}")
        print("=" * 70)


async def main():
    """Main entry point."""
    # Parse command line arguments
    limit = None
    if len(sys.argv) > 1:
        if sys.argv[1] in ["--limit", "-l"] and len(sys.argv) > 2:
            limit = int(sys.argv[2])
            print(f"Limiting import to {limit} foods per dataset")

    importer = USDAImporter(limit=limit)
    await importer.run()


if __name__ == "__main__":
    asyncio.run(main())
