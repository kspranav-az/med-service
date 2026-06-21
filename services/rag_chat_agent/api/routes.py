"""HTTP routes for the RAG Chat Agent."""

from __future__ import annotations

from fastapi import APIRouter

from shared.logging import get_logger
from shared.models import ChatRequest, ChatResponse
from shared.observability import observability

logger = get_logger(__name__)
router = APIRouter(tags=["chat"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "rag_chat_agent"}


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Answer a medical question using retrieval-augmented generation.

    This is a stub implementation for Phase 1. The full pipeline (retrieval,
    reranking, LLM generation) will be implemented in Phase 2/3.
    """
    trace_id = observability.trace_id()
    logger.info(
        "chat_request_received",
        extra={
            "query": request.query,
            "trace_id": trace_id,
        },
    )

    return ChatResponse(
        answer=(f"This is a placeholder answer. The RAG pipeline will answer: '{request.query}'"),
        confidence=0.0,
        trace_id=trace_id,
        reranker_used=request.reranker,
        cached=False,
    )
