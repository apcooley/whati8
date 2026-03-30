"""Body size limit middleware.

Rejects requests with bodies exceeding the configured maximum size.
Returns 413 Payload Too Large with a JSON error body.
"""

import json

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from whati8.config import settings


_SKIP_METHODS = {"GET", "HEAD", "OPTIONS"}

# Paths that need a larger body limit (e.g., file uploads)
# Include both forms: with and without the /api/v1 prefix.
# Starlette middleware may see the path with or without the prefix
# depending on how the app is mounted.
_LARGE_BODY_PATHS = {"/api/v1/photo/recognize", "/photo/recognize"}
_LARGE_BODY_MAX = 10 * 1024 * 1024  # 10MB

_ERROR_BODY = json.dumps(
    {
        "error": {
            "message": "Request body too large",
            "type": "payload_too_large",
            "status_code": 413,
        }
    }
).encode()


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces a maximum request body size."""

    def __init__(self, app, max_body_size: int | None = None) -> None:
        super().__init__(app)
        self.max_body_size = max_body_size if max_body_size is not None else settings.max_body_size

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in _SKIP_METHODS:
            return await call_next(request)

        # Use larger limit for upload paths
        max_size = (
            _LARGE_BODY_MAX
            if request.url.path in _LARGE_BODY_PATHS
            else self.max_body_size
        )

        # Fast-path: check Content-Length header first
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                size = int(content_length)
            except ValueError:
                size = 0
            if size > max_size:
                return Response(
                    content=_ERROR_BODY,
                    status_code=413,
                    media_type="application/json",
                )

        # Slow-path: no Content-Length (chunked/streaming) — buffer and check
        else:
            chunks: list[bytes] = []
            total = 0
            async for chunk in request.stream():
                total += len(chunk)
                if total > max_size:
                    return Response(
                        content=_ERROR_BODY,
                        status_code=413,
                        media_type="application/json",
                    )
                chunks.append(chunk)

            # Replace the request body with the buffered bytes so downstream
            # middleware/handlers can read it normally.
            body = b"".join(chunks)

            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}

            request._receive = receive  # noqa: SLF001

        return await call_next(request)
