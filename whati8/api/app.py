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
        response = await call_next(request)

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
        if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
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
    app = FastAPI(
        title="whati8 API",
        description="AI-powered food and nutrition tracker",
        version="0.1.0",
        docs_url="/docs",  # Swagger UI
        redoc_url="/redoc",  # ReDoc
        lifespan=lifespan,
    )

    # 2. Add security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # 3. Add CORS middleware (for frontend access)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,  # Configurable via ALLOWED_ORIGINS env var
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

    # 6. Include routers
    app.include_router(auth_router, prefix="/auth", tags=["authentication"])
    app.include_router(food_router)  # Prefix already in router definition
    app.include_router(food_log_router)  # Prefix already in router definition
    app.include_router(profile_router)
    app.include_router(recipe_router)  # Prefix already in router definition
    app.include_router(summary_config_router)
    app.include_router(photo_router)  # Prefix already in router definition
    app.include_router(agent_router)  # Prefix already in router definition

    # 7. Health check endpoint
    @app.get("/health", tags=["health"])
    async def health_check():
        """Health check endpoint for monitoring."""
        return {"status": "healthy"}

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
