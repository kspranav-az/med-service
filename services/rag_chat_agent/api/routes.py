"""HTTP routes for the RAG Chat Agent."""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, HTTPException

from services.rag_chat_agent.service.rag_service import RAGService
from shared.config import settings
from shared.logging import get_logger
from shared.models import ChatRequest, ChatResponse
from shared.observability import observability

logger = get_logger(__name__)
router = APIRouter(tags=["chat"])


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
async def chat(request: ChatRequest) -> ChatResponse:
    """Answer a medical question using retrieval-augmented generation."""
    if not settings.openai_api_key and not settings.anthropic_api_key and not settings.kimi_api_key:
        raise HTTPException(
            status_code=503,
            detail="No LLM API key configured. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or KIMI_API_KEY.",
        )

    trace = observability.start_trace(
        name="rag_chat",
        metadata={
            "query": request.query,
            "model": request.model or settings.default_llm_model,
            "reranker": request.reranker,
            "top_k": request.top_k,
            "rerank_top_k": request.rerank_top_k,
            "use_cache": request.use_cache,
        },
    )
    trace_id = getattr(trace, "id", observability.trace_id())
    logger.info(
        "chat_request_received",
        extra={
            "query": request.query,
            "trace_id": trace_id,
        },
    )

    service = get_rag_service()
    response = await service.answer(request, trace=trace)
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
