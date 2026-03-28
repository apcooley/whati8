"""Health check endpoint for whati8 API."""

from fastapi import APIRouter
from sqlalchemy import text

from importlib.metadata import version, PackageNotFoundError

from whati8.database import AsyncSessionLocal

router = APIRouter(tags=["health"])

try:
    APP_VERSION = version("whati8")
except PackageNotFoundError:
    APP_VERSION = "dev"


@router.get("/health")
async def health_check():
    """Health check endpoint — no auth required."""
    db_status = "ok"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    status = "healthy" if db_status == "ok" else "unhealthy"
    return {"status": status, "db": db_status, "version": APP_VERSION}
