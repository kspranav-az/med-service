"""HTTP routes for the Semantic Autocomplete service."""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Request

from services.autocomplete.service.autocomplete_service import AutocompleteService
from shared.logging import get_logger
from shared.models import AutocompleteRequest, AutocompleteResponse
from shared.observability import observability
from shared.rate_limit import RateLimiter, RateLimitExceededError

logger = get_logger(__name__)
router = APIRouter(tags=["autocomplete"])

_autocomplete_service: AutocompleteService | None = None
_autocomplete_limiter = RateLimiter.for_autocomplete()


def _get_service() -> AutocompleteService:
    """Return the singleton autocomplete service."""
    global _autocomplete_service
    if _autocomplete_service is None:
        _autocomplete_service = AutocompleteService()
    return _autocomplete_service


@router.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "autocomplete"}


@router.post("/autocomplete", response_model=AutocompleteResponse)
async def autocomplete(request: Request, req: AutocompleteRequest) -> AutocompleteResponse:
    """Return medical term suggestions for the given prefix."""
    trace_id = observability.trace_id()
    logger.info(
        "autocomplete_request_received",
        extra={
            "query": req.query,
            "field_types": req.field_types,
            "trace_id": trace_id,
        },
    )

    identifier = request.client.host if request.client else "anonymous"
    try:
        await _autocomplete_limiter.check(identifier)
    except RateLimitExceededError as exc:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc

    start = time.perf_counter()
    service = _get_service()
    response = await service.complete(req)
    response.latency_ms = round((time.perf_counter() - start) * 1000, 2)

    return response
