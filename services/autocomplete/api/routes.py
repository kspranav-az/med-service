"""HTTP routes for the Semantic Autocomplete service."""

from __future__ import annotations

import time

from fastapi import APIRouter

from shared.logging import get_logger
from shared.models import AutocompleteRequest, AutocompleteResponse, AutocompleteResult
from shared.observability import observability

logger = get_logger(__name__)
router = APIRouter(tags=["autocomplete"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "autocomplete"}


@router.post("/autocomplete", response_model=AutocompleteResponse)
async def autocomplete(request: AutocompleteRequest) -> AutocompleteResponse:
    """Return medical term suggestions for the given prefix.

    This is a stub implementation for Phase 1. The trie + vector + RRF
    pipeline will be implemented in Phase 4.
    """
    start = time.perf_counter()
    trace_id = observability.trace_id()
    logger.info(
        "autocomplete_request_received",
        extra={
            "query": request.query,
            "field_types": request.field_types,
            "trace_id": trace_id,
        },
    )

    latency_ms = (time.perf_counter() - start) * 1000

    return AutocompleteResponse(
        query=request.query,
        field_types=request.field_types,
        results=[
            AutocompleteResult(
                term=request.query,
                cui=None,
                tuis=[],
                aliases=[],
                match_type="prefix",
                score=1.0,
            ),
        ],
        latency_ms=latency_ms,
        cached=False,
    )
