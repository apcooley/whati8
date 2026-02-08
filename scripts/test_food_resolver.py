#!/usr/bin/env python3
"""Test script for AI-powered food resolution endpoint."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from whati8.database import AsyncSessionLocal
from whati8.services.food_resolver import FoodResolverService


async def test_food_resolver():
    """Test the food resolver service."""
    print("=== whati8 Food Resolver Service Test ===\n")

    async with AsyncSessionLocal() as db:
        # Test Case 1: Simple breakfast
        print("Test Case 1: Simple breakfast input")
        print("Input: 'I had 2 eggs and toast for breakfast'\n")

        try:
            response = await FoodResolverService.resolve_foods(
                db=db,
                text="I had 2 eggs and toast for breakfast",
                max_matches_per_item=3,
            )

            print("✓ Parsed successfully")
            print(f"  Overall confidence: {response.overall_confidence}")
            print(f"  Resolved items: {len(response.resolved_items)}")
            print(
                f"  Meal context: {response.meal_context.meal_name if response.meal_context else 'None'}"
            )
            print()

            for i, item in enumerate(response.resolved_items, 1):
                print(f"  Item {i}: {item.parsed_item.food_name}")
                print(
                    f"    Quantity: {item.parsed_item.quantity} {item.parsed_item.unit}"
                )
                print(f"    Confidence: {item.parsed_item.confidence}")
                print(f"    Status: {item.status}")
                print(f"    Matches: {len(item.matches)}")
                if item.matches:
                    for match in item.matches[:2]:  # Show top 2
                        print(
                            f"      - {match.name} (similarity: {match.similarity_score})"
                        )
                print()
        except Exception as e:
            print(f"❌ Error: {e}\n")
            import traceback

            traceback.print_exc()
            return

        # Test Case 2: Measured dinner
        print("\nTest Case 2: Measured dinner")
        print("Input: '8oz grilled chicken breast with broccoli'\n")

        try:
            response = await FoodResolverService.resolve_foods(
                db=db,
                text="8oz grilled chicken breast with broccoli",
                max_matches_per_item=3,
            )

            print("✓ Parsed successfully")
            print(f"  Overall confidence: {response.overall_confidence}")
            print(f"  Resolved items: {len(response.resolved_items)}")
            print()

            for i, item in enumerate(response.resolved_items, 1):
                print(f"  Item {i}: {item.parsed_item.food_name}")
                print(
                    f"    Quantity: {item.parsed_item.quantity} {item.parsed_item.unit}"
                )
                print(f"    Confidence: {item.parsed_item.confidence}")
                print(f"    Status: {item.status}")
                print(f"    Matches: {len(item.matches)}")
                if item.matches:
                    print(
                        f"      Top match: {item.matches[0].name} (similarity: {item.matches[0].similarity_score})"
                    )
                print()
        except Exception as e:
            print(f"❌ Error: {e}\n")
            import traceback

            traceback.print_exc()
            return

        # Test Case 3: Ambiguous input
        print("\nTest Case 3: Ambiguous input")
        print("Input: 'had some chicken and rice'\n")

        try:
            response = await FoodResolverService.resolve_foods(
                db=db, text="had some chicken and rice", max_matches_per_item=3
            )

            print("✓ Parsed successfully")
            print(f"  Overall confidence: {response.overall_confidence}")
            print(f"  Resolved items: {len(response.resolved_items)}")
            print()

            for i, item in enumerate(response.resolved_items, 1):
                print(f"  Item {i}: {item.parsed_item.food_name}")
                print(
                    f"    Quantity: {item.parsed_item.quantity} {item.parsed_item.unit}"
                )
                print(
                    f"    Confidence: {item.parsed_item.confidence} (expected <0.7 for vague input)"
                )
                print(f"    Status: {item.status}")
                print()
        except Exception as e:
            print(f"❌ Error: {e}\n")
            import traceback

            traceback.print_exc()
            return

        # Test Case 4: Invalid input
        print("\nTest Case 4: Error handling - invalid input")
        print("Input: 'xyz'\n")

        try:
            response = await FoodResolverService.resolve_foods(
                db=db, text="xyz", max_matches_per_item=3
            )
            print("⚠ Should have raised an error for vague input")
        except ValueError as e:
            print(f"✓ Correctly raised ValueError: {e}\n")
        except Exception as e:
            print(f"❌ Unexpected error: {e}\n")
            import traceback

            traceback.print_exc()

    print("\n=== All test cases completed ===")
    print("\nNext steps:")
    print("  1. Start server: uv run python -m whati8 serve --reload")
    print("  2. Run bash tests: ./scripts/test_food_resolver.sh")
    print("  3. Check Swagger UI: http://localhost:8000/docs")


if __name__ == "__main__":
    asyncio.run(test_food_resolver())
