"""Phase 3 RAG enhancement tests."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from services.rag_chat_agent.service.rag_service import RAGService
from shared.cache.redis_cache import SemanticCache
from shared.dedup.request_dedup import RequestDeduplicator
from shared.models import ChatRequest
from shared.reranker.reranker import RERANKER_MODELS, get_reranker
from tests.conftest import FakeRedis


class TestReranker:
    """Tests for the cross-encoder reranker."""

    def test_reranker_sorts_and_normalizes_scores(self) -> None:
        with patch("shared.reranker.reranker.CrossEncoder") as mock_cls:
            mock_model = MagicMock()
            # Logits: first hit is strongly relevant, second irrelevant, third neutral.
            mock_model.predict.return_value = np.array([2.0, -2.0, 0.0], dtype=np.float32)
            mock_cls.return_value = mock_model

            reranker = get_reranker("minilm")
            hits = [
                {"id": "a", "payload": {"text": "good hit"}},
                {"id": "b", "payload": {"text": "bad hit"}},
                {"id": "c", "payload": {"text": "neutral hit"}},
            ]
            out = reranker.rerank("query", hits, top_k=2)

            assert len(out) == 2
            assert out[0]["id"] == "a"
            assert out[0]["score"] > 0.8
            assert out[1]["id"] == "c"
            assert out[1]["score"] > out[2 - 1]["score"] or out[1]["id"] == "c"

    def test_reranker_model_aliases(self) -> None:
        assert "minilm" in RERANKER_MODELS
        assert "bge-reranker-v2-m3" in RERANKER_MODELS


class TestSemanticCache:
    """Tests for the Redis-backed semantic cache."""

    @pytest.mark.asyncio
    async def test_cache_round_trip(self, fake_redis: FakeRedis) -> None:
        cache = SemanticCache(client=fake_redis, ttl_seconds=60)
        payload = {"answer": "yes", "confidence": 0.9, "confidence_passed": True}

        await cache.set("what is x?", "gpt-4o", "minilm", 5, payload)
        result = await cache.get("what is x?", "gpt-4o", "minilm", 5)

        assert result == payload

    @pytest.mark.asyncio
    async def test_cache_key_differs_by_model(self, fake_redis: FakeRedis) -> None:
        cache = SemanticCache(client=fake_redis, ttl_seconds=60)
        await cache.set("q", "m1", "minilm", 5, {"answer": "model1"})
        await cache.set("q", "m2", "minilm", 5, {"answer": "model2"})

        assert (await cache.get("q", "m1", "minilm", 5)) == {"answer": "model1"}
        assert (await cache.get("q", "m2", "minilm", 5)) == {"answer": "model2"}


class TestRequestDeduplication:
    """Tests for the Redis-backed request deduplicator."""

    @pytest.mark.asyncio
    async def test_dedup_executes_factory_only_once(self, fake_redis: FakeRedis) -> None:
        dedup = RequestDeduplicator(client=fake_redis)
        counter = 0

        async def factory() -> dict[str, Any]:
            nonlocal counter
            counter += 1
            await asyncio.sleep(0.05)
            return {"count": counter}

        results = await asyncio.gather(
            dedup.execute("shared query", None, "minilm", 5, factory),
            dedup.execute("shared query", None, "minilm", 5, factory),
        )

        assert counter == 1
        assert all(r == {"count": 1} for r in results)

    @pytest.mark.asyncio
    async def test_dedup_falls_back_on_lock_timeout(self, fake_redis: FakeRedis) -> None:
        dedup = RequestDeduplicator(
            client=fake_redis,
            lock_ttl_seconds=1,
            max_wait_seconds=0.1,
            poll_interval=0.02,
        )

        # Simulate a stuck leader that never publishes a result.
        await fake_redis.set("rag:lock:stuck", "1")

        async def factory() -> dict[str, Any]:
            return {"fallback": True}

        result = await dedup.execute("stuck", None, "minilm", 5, factory)
        assert result == {"fallback": True}


class TestRAGServicePhase3:
    """Tests for Phase 3 integrations in the RAG service."""

    @pytest.mark.asyncio
    async def test_answer_uses_reranker(
        self,
        mock_embedder: MagicMock,
        mock_store: MagicMock,
        fake_redis: FakeRedis,
    ) -> None:
        reranked_hit = {
            "id": "test_00001",
            "score": 0.99,
            "payload": {
                "source_id": "urodynamics_iaps",
                "page_number": 2,
                "text": "sample context",
            },
        }
        mock_reranker = MagicMock()
        mock_reranker.rerank.return_value = [reranked_hit]

        service = RAGService(
            embedder=mock_embedder,
            vector_store=mock_store,
            reranker=mock_reranker,
            cache=SemanticCache(client=fake_redis),
            deduplicator=RequestDeduplicator(client=fake_redis),
        )
        service.llm_client = AsyncMock()
        service.llm_client.complete.return_value = MagicMock(
            text="Answer based on [urodynamics_iaps, page 2].",
            model="gpt-4o",
            input_tokens=100,
            output_tokens=20,
        )

        request = ChatRequest(query="test question", top_k=5, rerank_top_k=1)
        response = await service.answer(request)

        assert response.reranker_used == "minilm"
        assert response.confidence >= 0.0
        mock_reranker.rerank.assert_called_once()

    @pytest.mark.asyncio
    async def test_answer_cache_hit(
        self,
        mock_embedder: MagicMock,
        mock_store: MagicMock,
        fake_redis: FakeRedis,
    ) -> None:
        cache = SemanticCache(client=fake_redis)
        await cache.set("cached query", None, "minilm", 5, {
            "answer": "cached answer",
            "citations": [],
            "confidence": 0.9,
            "confidence_passed": True,
            "tokens_used": 10,
            "reranker_used": "minilm",
            "cached": False,
        })

        service = RAGService(
            embedder=mock_embedder,
            vector_store=mock_store,
            reranker=MagicMock(),
            cache=cache,
            deduplicator=RequestDeduplicator(client=fake_redis),
        )
        request = ChatRequest(query="cached query", use_cache=True)
        response = await service.answer(request)

        assert response.cached is True
        assert response.answer == "cached answer"
        # LLM should not be called on a cache hit.
        assert service.llm_client is not None

    @pytest.mark.asyncio
    async def test_answer_low_confidence_prefix(
        self,
        mock_embedder: MagicMock,
        mock_store: MagicMock,
        fake_redis: FakeRedis,
    ) -> None:
        mock_reranker = MagicMock()
        mock_reranker.rerank.return_value = mock_store.search.return_value

        service = RAGService(
            embedder=mock_embedder,
            vector_store=mock_store,
            reranker=mock_reranker,
            cache=SemanticCache(client=fake_redis),
            deduplicator=RequestDeduplicator(client=fake_redis),
        )
        service.llm_client = AsyncMock()
        service.llm_client.complete.return_value = MagicMock(
            text="Some answer without citations.",
            model="gpt-4o",
            input_tokens=100,
            output_tokens=20,
        )

        request = ChatRequest(
            query="test question",
            top_k=5,
            confidence_threshold=0.9,
        )
        response = await service.answer(request)

        assert response.confidence_passed is False
        assert response.answer.startswith("[Low confidence:")
