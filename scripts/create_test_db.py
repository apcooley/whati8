#!/usr/bin/env python3
"""Create test database for pytest."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


from whati8.config import settings  # noqa: E402


async def create_test_database():
    """Create whati8_test database if it doesn't exist."""
    import asyncpg

    # Parse database URL
    db_url = str(settings.database_url)
    # Extract connection params (postgresql+asyncpg://user:pass@host:port/db)
    db_url = db_url.replace("postgresql+asyncpg://", "")
    parts = db_url.split("@")
    user_pass = parts[0].split(":")
    host_db = parts[1].split("/")
    host_port = host_db[0].split(":")

    user = user_pass[0]
    password = user_pass[1] if len(user_pass) > 1 else None
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 5432

    # Connect to postgres database
    conn = await asyncpg.connect(
        user=user, password=password, host=host, port=port, database="postgres"
    )

    try:
        # Check if test database exists
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = 'whati8_test'"
        )

        if exists:
            print("✓ Test database 'whati8_test' already exists")
        else:
            # Create test database
            await conn.execute("CREATE DATABASE whati8_test")
            print("✓ Created test database 'whati8_test'")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(create_test_database())
