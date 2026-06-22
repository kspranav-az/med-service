"""Shared pytest fixtures for the RAG pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from shared.embeddings.embedder import Embedder
from shared.vector_store.qdrant_store import QdrantVectorStore


class FakeRedis:
    """In-memory async Redis client for unit tests."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._locks: set[str] = set()

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def set(
        self,
        key: str,
        value: str,
        nx: bool = False,
        ex: int | None = None,
    ) -> bool | None:
        if nx and key in self._data:
            return None
        self._data[key] = value
        return True

    async def setex(self, key: str, seconds: int, value: str) -> None:
        self._data[key] = value

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)

    async def close(self) -> None:
        pass


@pytest.fixture
def fake_redis() -> FakeRedis:
    """Return a fresh fake Redis client."""
    return FakeRedis()


@pytest.fixture
def mock_embedder() -> MagicMock:
    """Return a mock embedder that produces a unit vector."""
    embedder = MagicMock(spec=Embedder)
    embedder.dimension = 768
    embedder.encode.return_value = np.array([[1.0] + [0.0] * 767], dtype=np.float32)
    return embedder


@pytest.fixture
def mock_store() -> MagicMock:
    """Return a mock Qdrant vector store with one hit."""
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
