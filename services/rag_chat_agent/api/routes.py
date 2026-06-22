"""HTTP routes for the RAG Chat Agent."""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, HTTPException, Request

from services.rag_chat_agent.service.rag_service import RAGService
from shared.config import settings
from shared.logging import get_logger
from shared.models import ChatRequest, ChatResponse
from shared.observability import observability
from shared.rate_limit import RateLimiter, RateLimitExceededError

logger = get_logger(__name__)
router = APIRouter(tags=["chat"])

_chat_limiter = RateLimiter.for_chat()


@lru_cache(maxsize=1)
def get_rag_service() -> RAGService:
    """Return the singleton RAG service instance.

    The embedder and reranker are loaded lazily and reused across requests.
    """
    return RAGService()


@router.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "rag_chat_agent"}


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, req: ChatRequest) -> ChatResponse:
    """Answer a medical question using retrieval-augmented generation."""
    if not settings.openai_api_key and not settings.anthropic_api_key and not settings.kimi_api_key:
        raise HTTPException(
            status_code=503,
            detail="No LLM API key configured. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or KIMI_API_KEY.",
        )

    identifier = request.client.host if request.client else "anonymous"
    try:
        await _chat_limiter.check(identifier)
    except RateLimitExceededError as exc:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc

    trace = observability.start_trace(
        name="rag_chat",
        metadata={
            "query": req.query,
            "model": req.model or settings.default_llm_model,
            "reranker": req.reranker,
            "top_k": req.top_k,
            "rerank_top_k": req.rerank_top_k,
            "use_cache": req.use_cache,
        },
    )
    trace_id = getattr(trace, "id", observability.trace_id())
    logger.info(
        "chat_request_received",
        extra={
            "query": req.query,
            "trace_id": trace_id,
        },
    )

    service = get_rag_service()
    response = await service.answer(req, trace=trace)
    response.trace_id = trace_id

    try:
        trace.update(
            metadata={
                "confidence": response.confidence,
                "confidence_passed": response.confidence_passed,
                "citations": len(response.citations),
                "tokens_used": response.tokens_used,
                "cached": response.cached,
                "reranker_used": response.reranker_used,
            },
            output=response.answer,
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("trace_update_failed", extra={"error": str(exc)})

    return response
