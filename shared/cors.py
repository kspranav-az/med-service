"""CORS helpers that attach headers even to error responses."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from shared.config import settings


def get_cors_origins() -> list[str]:
    """Return the parsed list of allowed CORS origins."""
    return [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]


def _add_cors_headers(
    response: Response, origin: str | None, allowed_origins: list[str]
) -> Response:
    """Add CORS headers when the request origin is allowed."""
    if origin and (origin in allowed_origins or "*" in allowed_origins):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


async def http_exception_handler(request: Request, exc: Exception) -> Response:
    """Handle HTTP exceptions and add CORS headers."""
    if isinstance(exc, StarletteHTTPException):
        response = JSONResponse(
            {"detail": exc.detail},
            status_code=exc.status_code,
            headers=exc.headers or {},
        )
    else:
        response = JSONResponse({"detail": "Internal server error"}, status_code=500)
    return _add_cors_headers(response, request.headers.get("origin"), get_cors_origins())


async def general_exception_handler(request: Request, exc: Exception) -> Response:
    """Handle unexpected exceptions and add CORS headers."""
    detail = str(exc) if settings.is_development else "Internal server error"
    response = JSONResponse({"detail": detail}, status_code=500)
    return _add_cors_headers(response, request.headers.get("origin"), get_cors_origins())
