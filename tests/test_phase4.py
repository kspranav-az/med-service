"""Phase 4 autocomplete foundation tests."""

from __future__ import annotations

import json
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
import redis.asyncio as redis
from fastapi.testclient import TestClient

from services.autocomplete.api.main import app as autocomplete_app
from services.autocomplete.service.autocomplete_service import (
    AutocompleteCache,
    AutocompleteService,
)
from services.autocomplete.service.trie import EntityTrie
from shared.config import settings
from shared.entities import SciSpaCyEntityProvider
from shared.fusion.rrf import reciprocal_rank_fusion
from shared.fuzzy import FuzzyMatcher
from shared.models import AutocompleteRequest, AutocompleteResponse, Entity
from shared.rate_limit import RateLimiter, RateLimitExceededError
from shared.vector_store.entity_store import EntityVectorStore
from tests.conftest import FakeRedis


class TestEntityProvider:
    """Tests for the SciSpaCy entity provider."""

    def test_extract_entities(self) -> None:
        mock_nlp = MagicMock()
        mock_ent1 = MagicMock(text="diabetes mellitus", label_="DISEASE")
        mock_ent2 = MagicMock(text="insulin", label_="CHEMICAL")
        mock_nlp.return_value.ents = [mock_ent1, mock_ent2]

        with patch("spacy.load", return_value=mock_nlp):
            provider = SciSpaCyEntityProvider(model_name="en_core_sci_md")
            entities = provider.extract(
                "diabetes mellitus is treated with insulin",
                source_id="test",
            )

        assert any(
            e.name == "diabetes mellitus" and e.entity_type == "DISEASE" and e.cui is None
            for e in entities
        )
        assert any(
            e.name == "insulin" and e.entity_type == "CHEMICAL" and e.tuis == ["TUI-CHEMICAL"]
            for e in entities
        )


class TestTrie:
    """Tests for the entity trie."""

    def test_prefix_search(self) -> None:
        trie = EntityTrie()
        trie.insert("diabetes", {"name": "diabetes"})
        trie.insert("diabetic neuropathy", {"name": "diabetic neuropathy"})
        trie.insert("dialysis", {"name": "dialysis"})

        results = trie.prefix_search("diab", limit=10)
        assert len(results) == 2

    def test_prefix_search_empty(self) -> None:
        trie = EntityTrie()
        assert trie.prefix_search("xyz") == []


class TestFuzzyMatcher:
    """Tests for the fuzzy matcher."""

    def test_typo_match(self) -> None:
        candidates = [
            ("diabetes", "diabetes_value"),
            ("hypertension", "hypertension_value"),
            ("asthma", "asthma_value"),
        ]
        matcher = FuzzyMatcher(candidates)
        results: list[tuple[str, float]] = matcher.search(
            "diabetis", limit=3, score_cutoff=75
        )

        assert len(results) >= 1
        assert results[0][0] == "diabetes_value"
        assert results[0][1] > 75


class TestRRF:
    """Tests for reciprocal rank fusion."""

    def test_fusion_boosts_shared_items(self) -> None:
        list_a = ["a", "b", "c"]
        list_b = ["b", "d", "e"]
        fused = reciprocal_rank_fusion([list_a, list_b], top_k=5)

        terms = [item for item, _score in fused]
        assert terms[0] == "b"


class TestRateLimiter:
    """Tests for the token-bucket rate limiter."""

    @pytest.mark.asyncio
    async def test_allow_within_burst(self, fake_redis: FakeRedis) -> None:
        limiter = RateLimiter(
            key_prefix="rl:test",
            max_requests=10,
            window_seconds=60,
            burst=3,
            client=cast(redis.Redis, fake_redis),
        )
        for _ in range(3):
            allowed, _remaining, _retry = await limiter.is_allowed("ip")
            assert allowed is True

    @pytest.mark.asyncio
    async def test_block_after_burst(self, fake_redis: FakeRedis) -> None:
        limiter = RateLimiter(
            key_prefix="rl:test",
            max_requests=10,
            window_seconds=60,
            burst=2,
            client=cast(redis.Redis, fake_redis),
        )
        await limiter.is_allowed("ip")
        await limiter.is_allowed("ip")

        with pytest.raises(RateLimitExceededError):
            await limiter.check("ip")


class TestEntityStore:
    """Integration tests for the entity vector store (require local Qdrant)."""

    @pytest.fixture(scope="module")
    def store(self) -> EntityVectorStore | None:
        try:
            store = EntityVectorStore()
            store.ensure_collection(dimension=768)
            return store
        except Exception:  # pragma: no cover
            return None

    def test_upsert_and_search(self, store: EntityVectorStore | None) -> None:
        if store is None:
            pytest.skip("Qdrant not available")

        store.delete_by_term("test entity")
        entities = [
            Entity(
                name="test entity",
                cui=None,
                tuis=["TUI-DISEASE"],
                aliases=["test alias"],
                source="test_source",
                entity_type="DISEASE",
            )
        ]
        embeddings = __import__("numpy").array([[1.0] + [0.0] * 767], dtype=__import__("numpy").float32)
        store.upsert_entities(entities, embeddings)

        results = store.search(embeddings[0], top_k=1)
        assert len(results) == 1
        assert results[0]["payload"]["term"] == "test entity"

        store.delete_by_term("test entity")


class TestAutocompleteService:
    """Tests for the autocomplete service."""

    @pytest.fixture
    def entity_file(self, tmp_path: Any) -> Any:
        path = tmp_path / "entities.json"
        path.write_text(
            json.dumps(
                [
                    Entity(
                        name="diabetes mellitus",
                        cui=None,
                        tuis=["TUI-DISEASE"],
                        aliases=["diabetes"],
                        source="test",
                        entity_type="DISEASE",
                    ).model_dump(mode="json"),
                    Entity(
                        name="hypertension",
                        cui=None,
                        tuis=["TUI-DISEASE"],
                        aliases=[],
                        source="test",
                        entity_type="DISEASE",
                    ).model_dump(mode="json"),
                ]
            )
        )
        return path

    @pytest.mark.asyncio
    async def test_prefix_match(self, entity_file: Any) -> None:
        service = AutocompleteService(
            entity_file=entity_file,
            vector_store=MagicMock(spec=EntityVectorStore),
            cache=AutocompleteCache(client=cast(redis.Redis, FakeRedis())),
        )
        request = AutocompleteRequest(
            query="diab",
            fuzzy=False,
            semantic_expansion=False,
            limit=5,
        )
        response = await service.complete(request)

        assert len(response.results) >= 1
        assert response.results[0].term == "diabetes mellitus"

    @pytest.mark.asyncio
    async def test_cache_hit(self, entity_file: Any) -> None:
        cache = AutocompleteCache(client=cast(redis.Redis, FakeRedis()))
        cached_response = AutocompleteResponse(
            query="dia",
            field_types="all",
            results=[],
            latency_ms=0.0,
            cached=False,
        )
        await cache.set("dia", [], False, False, 5, cached_response.model_dump(mode="json"))

        service = AutocompleteService(
            entity_file=entity_file,
            vector_store=MagicMock(spec=EntityVectorStore),
            cache=cache,
        )
        request = AutocompleteRequest(
            query="dia",
            fuzzy=False,
            semantic_expansion=False,
            limit=5,
        )
        response = await service.complete(request)

        assert response.cached is True


class TestAutocompleteEndpoint:
    """Tests for the /autocomplete HTTP endpoint."""

    def test_autocomplete_prefix(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
        import services.autocomplete.api.routes as routes

        entity_file = (
            tmp_path / "data" / "processed" / "entities" / "scispacy_entities.json"
        )
        entity_file.parent.mkdir(parents=True)
        entity_file.write_text(
            json.dumps(
                [
                    Entity(
                        name="diabetes mellitus",
                        cui=None,
                        tuis=["TUI-DISEASE"],
                        aliases=[],
                        source="test",
                        entity_type="DISEASE",
                    ).model_dump(mode="json"),
                ]
            )
        )
        monkeypatch.setattr(settings, "project_root", tmp_path)
        routes._autocomplete_service = None
        routes._autocomplete_limiter = RateLimiter.for_autocomplete(client=cast(redis.Redis, FakeRedis()))

        client = TestClient(autocomplete_app)
        response = client.post(
            "/api/v1/autocomplete",
            json={
                "query": "diab",
                "field_types": "all",
                "limit": 5,
                "fuzzy": False,
                "semantic_expansion": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "diab"
        assert any(r["term"] == "diabetes mellitus" for r in data["results"])

    def test_autocomplete_rate_limit(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Any,
    ) -> None:
        import services.autocomplete.api.routes as routes

        entity_file = (
            tmp_path / "data" / "processed" / "entities" / "scispacy_entities.json"
        )
        entity_file.parent.mkdir(parents=True)
        entity_file.write_text("[]")
        monkeypatch.setattr(settings, "project_root", tmp_path)
        routes._autocomplete_service = None
        routes._autocomplete_limiter = RateLimiter(
            key_prefix="rl:autocomplete",
            max_requests=60,
            window_seconds=60,
            burst=1,
            client=cast(redis.Redis, FakeRedis()),
        )

        client = TestClient(autocomplete_app)
        client.post("/api/v1/autocomplete", json={"query": "a"})
        response = client.post("/api/v1/autocomplete", json={"query": "b"})

        assert response.status_code == 429
