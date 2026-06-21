"""RAG service: retrieve relevant chunks and generate cited answers."""

from __future__ import annotations

import re
from typing import Any

from services.rag_chat_agent.service.llm_client import LLMClient, LLMResponse
from shared.embeddings.embedder import DEFAULT_MODEL, Embedder
from shared.logging import get_logger
from shared.models import ChatRequest, ChatResponse, Citation
from shared.observability import observability
from shared.vector_store.qdrant_store import QdrantVectorStore

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a medical research assistant. Answer the user's question using ONLY the provided context.
The context consists of excerpts from medical textbooks with source identifiers.

Rules:
1. Ground every claim in the provided context.
2. Cite sources inline using [source_id, page NUMBER].
3. If the context does not contain enough information, say so clearly and do not make up information.
4. Be concise but medically precise.

Context:
{context}
"""


def _format_context(retrieved: list[dict[str, Any]]) -> str:
    """Format retrieved chunks into a context string for the LLM."""
    blocks: list[str] = []
    for idx, hit in enumerate(retrieved, start=1):
        payload = hit.get("payload", {})
        text = payload.get("text", "")
        source_id = payload.get("source_id", "unknown")
        page = payload.get("page_number", "unknown")
        blocks.append(f"[{idx}] Source: {source_id}, Page: {page}\n{text}\n")
    return "\n".join(blocks)


def _extract_citations(text: str) -> list[tuple[str, int]]:
    """Extract [source_id, page N] citations from generated text."""
    pattern = re.compile(r"\[([^\]]+?),\s*page\s+(\d+)\]")
    return [(source_id, int(page)) for source_id, page in pattern.findall(text)]


class RAGService:
    """End-to-end RAG pipeline."""

    def __init__(
        self,
        embedder: Embedder | None = None,
        vector_store: QdrantVectorStore | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        """Initialise the RAG service.

        Args:
            embedder: Embedding model. Created lazily if not provided.
            vector_store: Qdrant vector store client.
            llm_client: LLM client for generation.
        """
        self._embedder = embedder
        self.vector_store = vector_store or QdrantVectorStore()
        self.llm_client = llm_client or LLMClient()

    @property
    def embedder(self) -> Embedder:
        """Lazy-load the embedding model."""
        if self._embedder is None:
            self._embedder = Embedder(model_name=DEFAULT_MODEL)
        return self._embedder

    async def retrieve(
        self,
        query: str,
        top_k: int = 20,
    ) -> list[dict[str, Any]]:
        """Retrieve the top-k relevant chunks for a query."""
        with observability.trace_span(name="rag_retrieve"):
            query_embedding = self.embedder.encode([query], show_progress=False)
            results = self.vector_store.search(
                query_embedding=query_embedding[0],
                top_k=top_k,
            )
            logger.info(
                "retrieved_chunks",
                extra={"query": query, "top_k": top_k, "results": len(results)},
            )
            return results

    async def generate(
        self,
        request: ChatRequest,
        retrieved: list[dict[str, Any]],
    ) -> ChatResponse:
        """Generate an answer from retrieved chunks."""
        with observability.trace_span(name="rag_generate"):
            if not retrieved:
                return ChatResponse(
                    answer="I could not find relevant context to answer this question.",
                    citations=[],
                    confidence=0.0,
                    trace_id=observability.trace_id(),
                    reranker_used=request.reranker,
                    cached=False,
                )

            context = _format_context(retrieved)
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT.format(context=context)},
                {"role": "user", "content": request.query},
            ]

            try:
                llm_response: LLMResponse = await self.llm_client.complete(
                    messages=messages,
                    model=request.model,
                    temperature=0.1,
                    max_tokens=1024,
                )
            except Exception as exc:
                logger.error("llm_generation_failed", extra={"error": str(exc)})
                return ChatResponse(
                    answer="An error occurred while generating the answer.",
                    citations=[],
                    confidence=0.0,
                    trace_id=observability.trace_id(),
                    reranker_used=request.reranker,
                    cached=False,
                )

            citations = self._build_citations(retrieved, llm_response.text)
            confidence = self._estimate_confidence(retrieved, citations)

            return ChatResponse(
                answer=llm_response.text,
                citations=citations,
                confidence=confidence,
                tokens_used=llm_response.input_tokens + llm_response.output_tokens,
                trace_id=observability.trace_id(),
                reranker_used=request.reranker,
                cached=False,
            )

    async def answer(self, request: ChatRequest) -> ChatResponse:
        """Run the full RAG pipeline for a chat request."""
        retrieved = await self.retrieve(request.query, top_k=request.top_k)
        return await self.generate(request, retrieved)

    def _build_citations(
        self,
        retrieved: list[dict[str, Any]],
        answer_text: str,
    ) -> list[Citation]:
        """Build Citation objects from inline citations in the answer."""
        cited = _extract_citations(answer_text)
        citations: list[Citation] = []

        for source_id, page in cited:
            # Find the highest-scoring chunk matching this source/page.
            best: dict[str, Any] | None = None
            for hit in retrieved:
                payload = hit.get("payload", {})
                matches = (
                    payload.get("source_id") == source_id and payload.get("page_number") == page
                )
                if matches and (best is None or hit.get("score", 0) > best.get("score", 0)):
                    best = hit

            if best is None:
                continue

            payload = best.get("payload", {})
            citations.append(
                Citation(
                    chunk_id=str(best.get("id", "")),
                    source_id=source_id,
                    source_title=None,
                    page=int(page) if isinstance(page, str) else page,
                    score=float(best.get("score", 0.0)),
                )
            )

        # Deduplicate while preserving order.
        seen: set[str] = set()
        unique: list[Citation] = []
        for citation in citations:
            key = f"{citation.chunk_id}:{citation.page}"
            if key not in seen:
                seen.add(key)
                unique.append(citation)

        return unique

    def _estimate_confidence(
        self,
        retrieved: list[dict[str, Any]],
        citations: list[Citation],
    ) -> float:
        """Estimate answer confidence from retrieval scores and citations."""
        if not retrieved:
            return 0.0
        top_score = max(hit.get("score", 0.0) for hit in retrieved)
        citation_ratio = len(citations) / max(len(retrieved), 1)
        return round(min(top_score * citation_ratio, 1.0), 2)
