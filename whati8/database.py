"""
Database connection setup for SQLAlchemy async engine.

Provides:
- Async engine with asyncpg driver
- AsyncSessionLocal factory for creating sessions
- get_db() dependency for FastAPI
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from whati8.config import settings

# Create async engine with asyncpg driver
_connect_args = {}
_db_url = str(settings.database_url)

# Fly.io internal Postgres doesn't use SSL — disable it for asyncpg
if "flycast" in _db_url or ".internal" in _db_url:
    _connect_args["ssl"] = False

# Cloud SQL Unix socket: extract host= query param for asyncpg
if "host=/cloudsql/" in _db_url:
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(_db_url)
    qs = parse_qs(parsed.query)
    socket_dir = qs.get("host", [None])[0]
    if socket_dir:
        _connect_args["host"] = socket_dir
        # Remove host from query string since it's now in connect_args
        # Rebuild URL without the host param (use localhost as placeholder)
        clean_url = _db_url.split("?")[0]
        settings.database_url = clean_url

engine: AsyncEngine = create_async_engine(
    settings.get_async_database_url(),
    echo=settings.debug,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle,
    pool_pre_ping=True,  # Verify connections before using
    connect_args=_connect_args,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions.

    Yields:
        AsyncSession: Database session with automatic commit/rollback/close

    Usage:
        @app.get("/items")
        async def read_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
