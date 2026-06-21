"""HTTP routes for the RAG Chat Agent."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from services.rag_chat_agent.service.rag_service import RAGService
from shared.config import settings
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
    """Answer a medical question using retrieval-augmented generation."""
    if not settings.openai_api_key and not settings.anthropic_api_key and not settings.kimi_api_key:
        raise HTTPException(
            status_code=503,
            detail="No LLM API key configured. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or KIMI_API_KEY.",
        )

    trace_id = observability.trace_id()
    logger.info(
        "chat_request_received",
        extra={
            "query": request.query,
            "trace_id": trace_id,
        },
    )

    service = RAGService()
    response = await service.answer(request)
    response.trace_id = trace_id
    return response
