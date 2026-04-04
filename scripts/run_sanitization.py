"""One-shot runner to execute sanitization + verification on a target database."""

import asyncio
import sys

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from whati8.scripts.sanitize_foods import (
    sanitize_usda_foods,
    sanitize_custom_foods,
    sanitize_recipe_foods,
)
from whati8.scripts.verify_sanitization import verify_sanitization


async def main(database_url: str) -> None:
    # Convert to async URL
    url = database_url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        async with session.begin():
            print("=== Sanitizing USDA foods ===")
            usda_stats = await sanitize_usda_foods(session)
            print(f"  Processed: {usda_stats['processed']}, Complete: {usda_stats['complete']}, Incomplete: {usda_stats['incomplete']}")

            print("\n=== Sanitizing custom foods ===")
            custom_stats = await sanitize_custom_foods(session)
            print(f"  Processed: {custom_stats['processed']}, Complete: {custom_stats['complete']}, Incomplete: {custom_stats['incomplete']}")

            print("\n=== Sanitizing recipe foods ===")
            recipe_stats = await sanitize_recipe_foods(session)
            print(f"  Processed: {recipe_stats['processed']}, Complete: {recipe_stats['complete']}, Incomplete: {recipe_stats['incomplete']}")

        # Verify in a new transaction
        async with session.begin():
            print("\n=== Verification ===")
            verify = await verify_sanitization(session)
            print(f"  USDA checked: {verify['usda_checked']}, failures: {verify['usda_failures']}")
            print(f"  Custom checked: {verify['custom_checked']}, failures: {verify['custom_failures']}")
            print(f"  Recipe checked: {verify['recipe_checked']}, failures: {verify['recipe_failures']}")
            print(f"  Null calories (USDA): {verify['null_calories_usda']}")
            print(f"  Incomplete foods: {verify['incomplete_count']}")

            if verify['failures']:
                print(f"\n  ⚠️  {len(verify['failures'])} failures:")
                for f in verify['failures'][:20]:
                    print(f"    - [{f['type']}] {f['name']}: {f['reason']}")
            else:
                print("\n  ✅ All foods verified successfully!")

    await engine.dispose()

    # Exit code
    total_failures = verify['usda_failures'] + verify['custom_failures'] + verify['recipe_failures']
    if total_failures > 0:
        print(f"\n❌ {total_failures} total failures")
        sys.exit(1)
    else:
        print("\n🏆 Sanitization complete and verified!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_sanitization.py <DATABASE_URL>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
