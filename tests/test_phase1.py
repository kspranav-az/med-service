"""Phase 1 foundation tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from services.autocomplete.api.main import app as autocomplete_app
from services.rag_chat_agent.api.main import app as rag_app
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
    """Tests for the RAG chat agent service stub."""

    @pytest.fixture(scope="module")
    def client(self) -> TestClient:
        return TestClient(rag_app)

    def test_health(self, client: TestClient) -> None:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_chat_stub(self, client: TestClient) -> None:
        request = ChatRequest(query="test question")
        response = client.post("/api/v1/chat", json=request.model_dump())
        assert response.status_code == 200
        data = response.json()
        assert "placeholder answer" in data["answer"]
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
