#!/usr/bin/env python3
"""
Verification script for whati8 domain model setup.

Tests that all components are properly configured:
- Configuration loading
- Model imports
- Database connection (if available)
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_config():
    """Test configuration loading."""
    print("Testing configuration...")
    try:
        from whati8.config import settings

        print("  ✓ Settings loaded")
        print(f"    - Database URL: {str(settings.database_url)[:30]}...")
        print(f"    - Debug mode: {settings.debug}")
        print(f"    - Pool size: {settings.db_pool_size}")
        return True
    except Exception as e:
        print(f"  ✗ Configuration failed: {e}")
        return False


def test_models():
    """Test model imports."""
    print("\nTesting model imports...")
    try:
        from whati8.models import (
            Base,
            User,
            Food,
            FoodLog,
            Recipe,
            RecipeIngredient,
            UserGoal,
        )

        models = [User, Food, FoodLog, Recipe, RecipeIngredient, UserGoal]
        print("  ✓ All models imported successfully")
        print(f"    - {len(models)} models defined")
        print(f"    - {len(Base.metadata.tables)} tables in metadata")

        # List tables
        for table_name in sorted(Base.metadata.tables.keys()):
            table = Base.metadata.tables[table_name]
            print(f"      • {table_name} ({len(table.columns)} columns)")

        return True
    except Exception as e:
        print(f"  ✗ Model import failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_database():
    """Test database connection."""
    print("\nTesting database connection...")
    try:
        from whati8.database import engine
        import asyncio

        async def check_connection():
            from sqlalchemy import text

            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT version()"))
                version = result.scalar()
                return version

        version = asyncio.run(check_connection())
        print("  ✓ Database connection successful")
        print(f"    - PostgreSQL version: {version.split(',')[0]}")
        return True
    except Exception as e:
        print(f"  ⚠ Database connection unavailable: {e}")
        print("    (This is OK if database hasn't been set up yet)")
        return None  # Not a failure, just not set up


def test_alembic():
    """Test Alembic configuration."""
    print("\nTesting Alembic setup...")
    try:
        from alembic.config import Config
        from alembic import command
        import io

        alembic_cfg = Config("alembic.ini")

        # Capture output
        output = io.StringIO()
        alembic_cfg.stdout = output

        # Check current revision (will fail if no database, that's OK)
        try:
            command.current(alembic_cfg)
            current = output.getvalue()
            print("  ✓ Alembic configured")
            if current.strip():
                print(f"    - Current revision: {current.strip()}")
            else:
                print("    - No migrations applied yet")
        except Exception:
            print("  ✓ Alembic configured (database not initialized)")

        # Check migrations directory
        versions_path = project_root / "alembic" / "versions"
        migrations = list(versions_path.glob("*.py"))
        migrations = [m for m in migrations if not m.name.startswith("__")]
        print(f"    - {len(migrations)} migration(s) defined")

        return True
    except Exception as e:
        print(f"  ✗ Alembic configuration failed: {e}")
        return False


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("whati8 Domain Model Setup Verification")
    print("=" * 60)

    results = {
        "Configuration": test_config(),
        "Models": test_models(),
        "Database": test_database(),
        "Alembic": test_alembic(),
    }

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    for test_name, result in results.items():
        if result is True:
            status = "✓ PASS"
        elif result is False:
            status = "✗ FAIL"
        else:
            status = "⚠ SKIP"
        print(f"  {status}: {test_name}")

    # Overall result
    failures = sum(1 for r in results.values() if r is False)

    print("\n" + "=" * 60)
    if failures == 0:
        print("✓ All critical tests passed!")
        if results["Database"] is None:
            print("\nNext step: Set up the database")
            print("  Run: ./scripts/setup_db.sh")
        else:
            print("\n✓ System ready for use!")
        return 0
    else:
        print(f"✗ {failures} test(s) failed")
        print("\nPlease check the errors above and fix configuration.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
