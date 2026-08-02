"""RAG service: retrieve relevant chunks and generate cited answers."""

from __future__ import annotations

import asyncio
import re
from typing import Any

from services.rag_chat_agent.service.llm_client import LLMClient, LLMResponse
from shared.cache.redis_cache import SemanticCache
from shared.config import settings
from shared.dedup.request_dedup import RequestDeduplicator
from shared.embeddings.embedder import DEFAULT_MODEL, Embedder
from shared.logging import get_logger
from shared.models import ChatRequest, ChatResponse, Citation
from shared.observability import observability
from shared.reranker.reranker import Reranker, get_reranker
from shared.vector_store.qdrant_store import QdrantVectorStore

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a medical research assistant. Answer the user's question using ONLY the provided context.
The context consists of excerpts from medical textbooks with source identifiers.

Rules:
1. Ground every claim in the provided context.
2. Cite sources inline using exactly this format: [source_id, page NUMBER].
   Examples: [hadidi_hypospadias, page 77] [coran_pediatric_surgery_part_3, page 378]
   When citing multiple sources in one place, separate them with semicolons: [hadidi_hypospadias, page 77; coran_pediatric_surgery_part_3, page 378]
3. Do not abbreviate or omit the word "page".
4. If the context does not contain enough information, say so clearly and do not make up information.
5. Be concise but medically precise.

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
    """Extract citations from generated text.

    Supports:
    - [source_id, page NUMBER]
    - [source_id, NUMBER] (fallback if the model omits "page")
    - Multiple citations separated by semicolons inside one bracket pair.
    """
    if not text:
        return []

    results: list[tuple[str, int]] = []
    # Match bracket groups that may contain semicolon-separated citations.
    bracket_pattern = re.compile(r"\[([^\]]+?)\]")
    # Match a single citation like "source_id, page 123" or "source_id, 123".
    citation_pattern = re.compile(r"([^,;]+?)\s*,\s*(?:page\s+)?(\d+)")

    for match in bracket_pattern.finditer(text):
        inner = match.group(1)
        for source_id, page in citation_pattern.findall(inner):
            source_id = source_id.strip()
            if source_id:
                results.append((source_id, int(page)))

    return results


class RAGService:
    """End-to-end RAG pipeline with reranking, caching, and deduplication."""

    def __init__(
        self,
        embedder: Embedder | None = None,
        vector_store: QdrantVectorStore | None = None,
        llm_client: LLMClient | None = None,
        reranker: Reranker | None = None,
        cache: SemanticCache | None = None,
        deduplicator: RequestDeduplicator | None = None,
    ) -> None:
        """Initialise the RAG service.

        Args:
            embedder: Embedding model. Created lazily if not provided.
            vector_store: Qdrant vector store client.
            llm_client: LLM client for generation.
            reranker: Cross-encoder reranker. Created lazily if not provided.
            cache: Redis-backed semantic cache.
            deduplicator: Redis-backed request deduplicator.
        """
        self._embedder = embedder
        self.vector_store = vector_store or QdrantVectorStore()
        self.llm_client = llm_client or LLMClient()
        self._reranker = reranker
        self._cache = cache or SemanticCache()
        self._deduplicator = deduplicator or RequestDeduplicator()

    @property
    def embedder(self) -> Embedder:
        """Lazy-load the embedding model."""
        if self._embedder is None:
            self._embedder = Embedder(model_name=DEFAULT_MODEL)
        return self._embedder

    @property
    def reranker(self) -> Reranker:
        """Lazy-load the cross-encoder reranker."""
        if self._reranker is None:
            self._reranker = get_reranker(settings.rag_default_reranker)
        return self._reranker

    async def retrieve(
        self,
        query: str,
        top_k: int = 20,
        trace: Any | None = None,
        use_keyword: bool = False,
    ) -> list[dict[str, Any]]:
        """Retrieve the top-k relevant chunks for a query.""

        Args:
            query: User query.
            top_k: Number of chunks to retrieve.
            trace: Optional Langfuse trace.
            use_keyword: Whether to fuse dense retrieval with keyword search.
        """

        with observability.trace_span(name="rag_retrieve", trace=trace):
            query_embedding = self.embedder.encode([query], show_progress=False)
            keyword_query = query if use_keyword else None
            results = self.vector_store.search(
                query_embedding=query_embedding[0],
                top_k=top_k,
                keyword_query=keyword_query,
            )
            logger.info(
                "retrieved_chunks",
                extra={
                    "query": query,
                    "top_k": top_k,
                    "hybrid": use_keyword,
                    "results": len(results),
                },
            )
            return results

    async def _rerank(
        self,
        request: ChatRequest,
        retrieved: list[dict[str, Any]],
        trace: Any | None = None,
    ) -> list[dict[str, Any]]:
        """Rerank retrieved chunks down to ``request.rerank_top_k``."""
        if not retrieved:
            return []

        with observability.trace_span(name="rag_rerank", trace=trace):
            try:
                reranked = await asyncio.to_thread(
                    self.reranker.rerank,
                    request.query,
                    retrieved,
                    top_k=request.rerank_top_k,
                )
                return reranked
            except Exception as exc:
                logger.warning(
                    "rerank_failed",
                    extra={"error": str(exc), "query": request.query},
                )
                return retrieved[: request.rerank_top_k]

    async def generate(
        self,
        request: ChatRequest,
        retrieved: list[dict[str, Any]],
        trace: Any | None = None,
    ) -> ChatResponse:
        """Generate an answer from retrieved chunks."""
        with observability.trace_span(name="rag_generate", trace=trace):
            if not retrieved:
                return ChatResponse(
                    answer="I could not find relevant context to answer this question.",
                    citations=[],
                    confidence=0.0,
                    confidence_passed=False,
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
                    max_tokens=request.max_tokens,
                )
            except Exception as exc:
                logger.error("llm_generation_failed", extra={"error": str(exc)})
                return ChatResponse(
                    answer="An error occurred while generating the answer.",
                    citations=[],
                    confidence=0.0,
                    confidence_passed=False,
                    trace_id=observability.trace_id(),
                    reranker_used=request.reranker,
                    cached=False,
                )

            if not llm_response.text:
                logger.warning("llm_returned_empty_answer")
                return ChatResponse(
                    answer="The model returned an empty answer.",
                    citations=[],
                    confidence=0.0,
                    confidence_passed=False,
                    trace_id=observability.trace_id(),
                    reranker_used=request.reranker,
                    cached=False,
                )

            citations = self._build_citations(retrieved, llm_response.text)
            confidence = self._estimate_confidence(retrieved, citations)
            confidence_passed = confidence >= request.confidence_threshold

            answer = llm_response.text
            if not confidence_passed:
                answer = f"[Low confidence: {confidence}] {answer}"

            return ChatResponse(
                answer=answer,
                citations=citations,
                confidence=confidence,
                confidence_passed=confidence_passed,
                tokens_used=llm_response.input_tokens + llm_response.output_tokens,
                trace_id=observability.trace_id(),
                reranker_used=request.reranker,
                cached=False,
            )

    async def answer(
        self,
        request: ChatRequest,
        trace: Any | None = None,
    ) -> ChatResponse:
        """Run the full RAG pipeline for a chat request.

        Handles caching and request deduplication. The returned response
        always carries the current trace identifier.
        """

        def _cache_args() -> tuple[str, str | None, str, int]:
            return (
                request.query,
                request.model,
                request.reranker,
                request.rerank_top_k,
            )

        if request.use_cache:
            cached = await self._cache.get(*_cache_args())
            if cached is not None:
                response = ChatResponse.model_validate(cached)
                response.cached = True
                response.trace_id = observability.trace_id()
                logger.info(
                    "cache_hit",
                    extra={"query": request.query, "trace_id": response.trace_id},
                )
                return response

        async def _compute() -> ChatResponse:
            retrieved = await self.retrieve(
                request.query,
                top_k=request.top_k,
                trace=trace,
                use_keyword=request.hybrid_search,
            )
            reranked = await self._rerank(request, retrieved, trace=trace)
            response = await self.generate(request, reranked, trace=trace)
            if request.use_cache:
                await self._cache.set(
                    *_cache_args(),
                    value=response.model_dump(mode="json"),
                )
            return response

        response = await self._deduplicator.execute(
            *_cache_args(),
            factory=_compute,
        )

        if isinstance(response, dict):
            response = ChatResponse.model_validate(response)

        response.trace_id = observability.trace_id()
        return response

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
        """Estimate answer confidence from retrieval/reranker scores and citations."""
        if not retrieved:
            return 0.0

        top_scores = [float(hit.get("score", 0.0)) for hit in retrieved[:5]]
        avg_score = sum(top_scores) / len(top_scores)
        # Citation factor ranges from 0.7 (no citations) to 1.0 (two or more).
        # A single strong citation therefore receives 0.85 of the score weight.
        citation_factor = 0.7 + 0.3 * min(len(citations) / 2.0, 1.0)
        return float(round(min(avg_score * citation_factor, 1.0), 2))
