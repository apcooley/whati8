"""Exception handlers for whati8 API."""
from anthropic import APIError as AnthropicAPIError
from fastapi import Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from jose.exceptions import JWTError
from sqlalchemy.exc import IntegrityError


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle FastAPI HTTP exceptions.

    Returns consistent JSON format for all HTTP errors.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "status_code": exc.status_code
        },
        headers=exc.headers
    )


async def jwt_exception_handler(request: Request, exc: JWTError) -> JSONResponse:
    """
    Handle JWT decode/validation errors.

    Returns 401 Unauthorized for all JWT-related errors.
    """
    return JSONResponse(
        status_code=401,
        content={
            "detail": "Invalid or expired token",
            "status_code": 401
        },
        headers={"WWW-Authenticate": "Bearer"}
    )


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """
    Handle database unique constraint violations.

    Parses error to determine if username or email is duplicate.
    Returns 409 Conflict with specific message.
    """
    error_msg = str(exc.orig).lower()

    if "unique constraint" in error_msg or "duplicate key" in error_msg:
        # Determine which field caused the conflict
        if "username" in error_msg:
            detail = "Username already exists"
        elif "email" in error_msg:
            detail = "Email already exists"
        else:
            detail = "A record with these values already exists"
    else:
        # Generic integrity error
        detail = "Database integrity error"

    return JSONResponse(
        status_code=409,
        content={
            "detail": detail,
            "status_code": 409
        }
    )


async def anthropic_error_handler(request: Request, exc: AnthropicAPIError) -> JSONResponse:
    """
    Handle Anthropic API errors.

    Returns appropriate status codes based on error type:
    - 401: Authentication errors
    - 429: Rate limit errors
    - 500: Other API errors
    """
    error_msg = str(exc).lower()

    if "authentication" in error_msg or "api key" in error_msg:
        status_code = 500  # Server config issue
        detail = "AI service authentication failed. Check server configuration."
    elif "rate_limit" in error_msg or "rate limit" in error_msg:
        status_code = 429
        detail = "AI service rate limit exceeded. Please try again later."
    else:
        status_code = 500
        detail = f"AI service error: {str(exc)}"

    return JSONResponse(
        status_code=status_code,
        content={
            "detail": detail,
            "status_code": status_code
        }
    )
