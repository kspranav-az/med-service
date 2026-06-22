"""Shared pytest fixtures for the RAG pipeline."""

from __future__ import annotations

from typing import Any
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
        self._counters: dict[str, int] = {}

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

    async def script_load(self, script: str) -> str:
        """Return a deterministic fake SHA for Lua scripts."""
        import hashlib

        return hashlib.sha256(script.encode("utf-8")).hexdigest()

    async def evalsha(
        self,
        sha: str,
        numkeys: int,
        key: str,
        *args: str,
    ) -> list[Any]:
        """Emulate a token-bucket script: allow up to ``burst`` requests."""
        burst = int(args[0]) if args else 1
        count = self._counters.get(key, 0)
        if count < burst:
            self._counters[key] = count + 1
            return [1, burst - count - 1]
        return [0, 0]

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
