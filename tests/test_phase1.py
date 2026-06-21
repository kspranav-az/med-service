"""Phase 1 foundation tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from services.autocomplete.api.main import app as autocomplete_app
from services.rag_chat_agent.api.main import app as rag_app
from shared.config import settings
from shared.corpus_client import load_manifest
from shared.models import AutocompleteRequest, ChatRequest, Source


class TestCorpusManifest:
    """Tests for the corpus manifest loader."""

    def test_load_manifest_returns_all_books(self) -> None:
        sources = load_manifest()
        assert len(sources) == 24
        assert all(isinstance(s, Source) for s in sources)

    def test_manifest_fields_mapped(self) -> None:
        first = load_manifest()[0]
        assert first.source_id == "arm_holschneider_2"
        assert first.filename == "arm_holschneider_2.pdf"
        assert first.total_pages == 477


class TestRagService:
    """Tests for the RAG chat agent service."""

    @pytest.fixture(scope="module")
    def client(self) -> TestClient:
        return TestClient(rag_app)

    def test_health(self, client: TestClient) -> None:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_chat_requires_llm_key(self, client: TestClient) -> None:
        response = client.post("/api/v1/chat", json={"query": "test"})
        assert response.status_code == 503
        assert "KIMI_API_KEY" in response.json()["detail"]

    def test_chat_returns_answer(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "openai_api_key", "sk-test")

        from shared.models import ChatResponse

        mock_response = ChatResponse(
            answer="Test answer based on context.",
            citations=[],
            confidence=0.85,
            tokens_used=120,
            trace_id="trace-test",
            reranker_used="minilm",
            cached=False,
        )

        with patch("services.rag_chat_agent.api.routes.RAGService") as mock_service_cls:
            instance = mock_service_cls.return_value
            instance.answer = AsyncMock(return_value=mock_response)

            request = ChatRequest(query="test question")
            response = client.post("/api/v1/chat", json=request.model_dump())

        assert response.status_code == 200
        data = response.json()
        assert "Test answer" in data["answer"]
        assert data["reranker_used"] == "minilm"


class TestAutocompleteService:
    """Tests for the autocomplete service stub."""

    @pytest.fixture(scope="module")
    def client(self) -> TestClient:
        return TestClient(autocomplete_app)

    def test_health(self, client: TestClient) -> None:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_autocomplete_stub(self, client: TestClient) -> None:
        request = AutocompleteRequest(query="myo", field_types="T047,T191")
        response = client.post("/api/v1/autocomplete", json=request.model_dump())
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "myo"
        assert len(data["results"]) == 1
