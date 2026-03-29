"""FastAPI application factory for whati8."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from anthropic import APIError as AnthropicAPIError
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from jose.exceptions import JWTError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.middleware.base import BaseHTTPMiddleware

from fastapi.responses import JSONResponse

from whati8.api.middleware.body_limit import BodySizeLimitMiddleware
from whati8.api.exceptions import (
    anthropic_error_handler,
    http_exception_handler,
    integrity_error_handler,
    jwt_exception_handler,
)
from whati8.api.routers.agent import router as agent_router
from whati8.api.routers.auth import router as auth_router
from whati8.api.routers.food import router as food_router
from whati8.api.routers.food_log import router as food_log_router
from whati8.api.routers.health import router as health_router
from whati8.api.routers.profile import router as profile_router
from whati8.api.routers.recipe import router as recipe_router
from whati8.api.routers.summary_config import router as summary_config_router
from whati8.api.routers.photo import router as photo_router
from whati8.config import settings
from whati8.database import AsyncSessionLocal
from whati8.logging_config import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifespan context manager for startup/shutdown events.
    
    Startup: Initialize logging and verify database connection.
    Shutdown: Cleanup resources (if any).
    """
    # === STARTUP ===
    setup_logging()
    logger.info("whati8 API starting up")
    logger.info(f"Allowed origins: {settings.allowed_origins}")
    logger.info(
        f"Rate limiting: {'enabled' if settings.rate_limit_enabled else 'disabled'}"
    )

    # Test database connection
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(select(1))
        logger.info("Database connection successful")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise  # Prevent startup if DB unavailable

    yield  # Application runs here

    # === SHUTDOWN ===
    logger.info("whati8 API shutting down")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Add security headers to response."""
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.error(f"Unhandled exception in middleware: {exc}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Enable XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content Security Policy - relaxed for docs endpoints
        # Swagger UI loads resources from CDN (cdn.jsdelivr.net)
        if request.url.path in ["/api/v1/docs", "/api/v1/redoc", "/api/v1/openapi.json"]:
            # Allow CDN resources for API documentation
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https://cdn.jsdelivr.net; "
                "font-src 'self' https://cdn.jsdelivr.net"
            )
        else:
            # Strict CSP for API endpoints
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'"
            )

        return response


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Sets up:
    - App metadata and documentation
    - CORS middleware for frontend access
    - Exception handlers for consistent error responses
    - API routers
    - Health check endpoint

    Returns:
        Configured FastAPI application instance
    """
    # 1. Initialize app with metadata and lifespan
    docs_url = "/api/v1/docs" if settings.docs_enabled else None
    redoc_url = "/api/v1/redoc" if settings.docs_enabled else None
    openapi_url = "/api/v1/openapi.json" if settings.docs_enabled else None
    app = FastAPI(
        title="whati8 API",
        description="AI-powered food and nutrition tracker",
        version="0.1.0",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )

    # 2. Add body size limit middleware FIRST (rejects oversized requests early)
    app.add_middleware(BodySizeLimitMiddleware)

    # 3a. Add security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # 3. Add CORS middleware (for frontend access)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_cors_origins(),  # Configurable via ALLOWED_ORIGINS env var
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # 4. Setup rate limiting
    if settings.rate_limit_enabled:
        limiter = Limiter(key_func=get_remote_address)
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # 5. Register exception handlers
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(JWTError, jwt_exception_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(AnthropicAPIError, anthropic_error_handler)

    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all handler so unhandled errors return 500 instead of crashing."""
        logger.error(f"Unhandled exception: {exc}")
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    app.add_exception_handler(Exception, generic_exception_handler)

    # 6. Include routers
    app.include_router(health_router)  # /health — no versioned prefix
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["authentication"])
    app.include_router(food_router, prefix="/api/v1")  # router has prefix="/foods"
    app.include_router(food_log_router, prefix="/api/v1")  # router has prefix="/logs"
    app.include_router(profile_router, prefix="/api/v1")  # router has prefix="/profile/foods"
    app.include_router(recipe_router, prefix="/api/v1")  # router has prefix="/recipes"
    app.include_router(summary_config_router, prefix="/api/v1")  # router has prefix="/summary-config"
    app.include_router(photo_router, prefix="/api/v1")  # router has prefix="/photo"
    app.include_router(agent_router, prefix="/api/v1")  # router has prefix="/agent"

    # 8. Mount static frontend files (MUST come last!)
    frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
        logger.info(f"Serving frontend from {frontend_dist}")
    else:
        logger.warning(f"Frontend dist not found at {frontend_dist}")

    return app


# Create app instance
app = create_app()
