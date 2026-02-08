"""Exception handlers for whati8 API."""

from anthropic import APIError as AnthropicAPIError
from fastapi import Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from jose.exceptions import JWTError
from sqlalchemy.exc import IntegrityError


class ErrorResponse:
    """Standardized error response builder."""

    @staticmethod
    def create(
        status_code: int,
        message: str,
        detail: str | None = None,
        error_type: str | None = None,
    ) -> JSONResponse:
        """
        Create a standardized error response.

        Args:
            status_code: HTTP status code
            message: Main error message
            detail: Optional additional details
            error_type: Optional error type classification

        Returns:
            JSONResponse with consistent error format
        """
        content = {
            "error": {
                "message": message,
                "type": error_type or "error",
                "status_code": status_code,
            }
        }
        if detail:
            content["error"]["detail"] = detail

        return JSONResponse(status_code=status_code, content=content)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle FastAPI HTTP exceptions.

    Returns consistent JSON format for all HTTP errors.
    """
    return ErrorResponse.create(
        status_code=exc.status_code,
        message=exc.detail if isinstance(exc.detail, str) else str(exc.detail),
        error_type="http_exception",
    )


async def jwt_exception_handler(request: Request, exc: JWTError) -> JSONResponse:
    """
    Handle JWT decode/validation errors.

    Returns 401 Unauthorized for all JWT-related errors.
    """
    return ErrorResponse.create(
        status_code=401,
        message="Invalid or expired token",
        error_type="authentication_error",
    )


async def integrity_error_handler(
    request: Request, exc: IntegrityError
) -> JSONResponse:
    """
    Handle database unique constraint violations.

    Parses error to determine if username or email is duplicate.
    Returns 409 Conflict with specific message.
    """
    error_msg = str(exc.orig).lower()

    if "unique constraint" in error_msg or "duplicate key" in error_msg:
        # Determine which field caused the conflict
        if "username" in error_msg:
            message = "Username already exists"
        elif "email" in error_msg:
            message = "Email already exists"
        else:
            message = "A record with these values already exists"
    else:
        # Generic integrity error
        message = "Database integrity error"

    return ErrorResponse.create(
        status_code=409,
        message=message,
        error_type="integrity_error",
    )


async def anthropic_error_handler(
    request: Request, exc: AnthropicAPIError
) -> JSONResponse:
    """
    Handle Anthropic API errors.

    Returns appropriate status codes based on error type:
    - 500: Authentication errors (server config issue)
    - 429: Rate limit errors
    - 500: Other API errors
    """
    error_msg = str(exc).lower()

    if "authentication" in error_msg or "api key" in error_msg:
        status_code = 500  # Server config issue
        message = "AI service authentication failed"
        detail = "Check server configuration"
    elif "rate_limit" in error_msg or "rate limit" in error_msg:
        status_code = 429
        message = "AI service rate limit exceeded"
        detail = "Please try again later"
    else:
        status_code = 500
        message = "AI service error"
        detail = str(exc)

    return ErrorResponse.create(
        status_code=status_code,
        message=message,
        detail=detail,
        error_type="ai_service_error",
    )
