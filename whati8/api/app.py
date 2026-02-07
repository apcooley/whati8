"""FastAPI application factory for whati8."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from jose.exceptions import JWTError
from sqlalchemy.exc import IntegrityError

from whati8.api.exceptions import (
    http_exception_handler,
    integrity_error_handler,
    jwt_exception_handler,
)
from whati8.api.routers.auth import router as auth_router


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
    # 1. Initialize app with metadata
    app = FastAPI(
        title="whati8 API",
        description="AI-powered food and nutrition tracker",
        version="0.1.0",
        docs_url="/docs",      # Swagger UI
        redoc_url="/redoc"     # ReDoc
    )

    # 2. Add CORS middleware (for frontend access)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: Configure from settings in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 3. Register exception handlers
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(JWTError, jwt_exception_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)

    # 4. Include routers
    app.include_router(auth_router, prefix="/auth", tags=["authentication"])

    # 5. Health check endpoint
    @app.get("/health", tags=["health"])
    async def health_check():
        """Health check endpoint for monitoring."""
        return {"status": "healthy"}

    return app


# Create app instance
app = create_app()
