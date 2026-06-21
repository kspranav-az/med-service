"""Phase 2 RAG pipeline tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from services.rag_chat_agent.service.rag_service import RAGService, _extract_citations
from shared.chunking import Chunker, ChunkingConfig
from shared.corpus_client import get_source_by_id, resolve_source_path
from shared.embeddings.embedder import Embedder
from shared.ingestion import ParserType, get_parser
from shared.models import ChatRequest, Chunk
from shared.vector_store.qdrant_store import QdrantVectorStore


class TestPyMuPDFParser:
    """Tests for the PyMuPDF parser."""

    def test_parse_small_pdf(self) -> None:
        source = get_source_by_id("urodynamics_iaps")
        assert source is not None

        parser = get_parser(source, ParserType.PYMUPDF)
        pages = parser.parse(resolve_source_path(source))

        assert len(pages) > 0
        assert all(page.source_id == "urodynamics_iaps" for page in pages)
        assert all(page.page_number > 0 for page in pages)
        assert all(len(page.text) > 0 for page in pages)


class TestChunker:
    """Tests for the token-based chunker."""

    def test_chunk_pages(self) -> None:
        from shared.ingestion.base import Page

        pages = [
            Page(source_id="test", page_number=1, text="word " * 100),
            Page(source_id="test", page_number=2, text="word " * 100),
        ]
        chunker = Chunker(ChunkingConfig(target_tokens=50, overlap_tokens=10))
        chunks = chunker.chunk_pages(pages, "test")

        assert len(chunks) >= 3
        assert all(isinstance(c, Chunk) for c in chunks)
        assert chunks[0].source_id == "test"
        assert chunks[0].chunk_id.startswith("test_")

    def test_chunker_overlap_constraint(self) -> None:
        with pytest.raises(ValueError):
            Chunker(ChunkingConfig(target_tokens=50, overlap_tokens=50))


class TestCitations:
    """Tests for citation extraction."""

    def test_extract_citations(self) -> None:
        text = "This is supported by [urodynamics_iaps, page 3] and [arm_holschneider_2, page 12]."
        citations = _extract_citations(text)
        assert citations == [
            ("urodynamics_iaps", 3),
            ("arm_holschneider_2", 12),
        ]


class TestRAGService:
    """Tests for the RAG service with mocked dependencies."""

    @pytest.fixture
    def mock_embedder(self) -> MagicMock:
        embedder = MagicMock(spec=Embedder)
        embedder.dimension = 768
        embedder.encode.return_value = np.array([[1.0] + [0.0] * 767], dtype=np.float32)
        return embedder

    @pytest.fixture
    def mock_store(self) -> MagicMock:
        store = MagicMock(spec=QdrantVectorStore)
        store.search.return_value = [
            {
                "id": "test_00001",
                "score": 0.95,
                "payload": {
                    "source_id": "urodynamics_iaps",
                    "page_number": 2,
                    "text": "sample context",
                },
            }
        ]
        return store

    @pytest.mark.asyncio
    async def test_answer_with_mocked_llm(
        self,
        mock_embedder: MagicMock,
        mock_store: MagicMock,
    ) -> None:
        service = RAGService(embedder=mock_embedder, vector_store=mock_store)
        service.llm_client = AsyncMock()
        service.llm_client.complete.return_value = MagicMock(
            text="Answer based on [urodynamics_iaps, page 2].",
            model="gpt-4o",
            input_tokens=100,
            output_tokens=20,
        )

        request = ChatRequest(query="test question", top_k=5)
        response = await service.answer(request)

        assert "Answer based on" in response.answer
        assert len(response.citations) == 1
        assert response.citations[0].source_id == "urodynamics_iaps"
        assert response.citations[0].page == 2
        assert response.tokens_used == 120

    @pytest.mark.asyncio
    async def test_answer_no_retrieved_chunks(
        self,
        mock_embedder: MagicMock,
    ) -> None:
        store = MagicMock(spec=QdrantVectorStore)
        store.search.return_value = []

        service = RAGService(embedder=mock_embedder, vector_store=store)
        request = ChatRequest(query="unknown topic", top_k=5)
        response = await service.answer(request)

        assert "could not find relevant context" in response.answer
        assert response.confidence == 0.0


class TestQdrantStore:
    """Integration tests for Qdrant vector store (require local Qdrant)."""

    @pytest.fixture(scope="module")
    def store(self) -> QdrantVectorStore | None:
        try:
            store = QdrantVectorStore()
            store.ensure_collection(dimension=768)
            return store
        except Exception:  # pragma: no cover
            return None

    def test_ensure_collection(self, store: QdrantVectorStore | None) -> None:
        if store is None:
            pytest.skip("Qdrant not available")
        assert store.count() >= 0

    def test_upsert_and_search(self, store: QdrantVectorStore | None) -> None:
        if store is None:
            pytest.skip("Qdrant not available")

        chunks = [
            Chunk(
                chunk_id="test_chunk_00001",
                source_id="test_source",
                chunk_index=0,
                page_number=1,
                text="diabetes treatment",
            )
        ]
        embeddings = np.array([[1.0] + [0.0] * 767], dtype=np.float32)
        store.upsert_chunks(chunks, embeddings)

        results = store.search(embeddings[0], top_k=1)
        assert len(results) == 1
        assert results[0]["payload"]["source_id"] == "test_source"

        store.delete_by_source("test_source")
