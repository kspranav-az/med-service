"""Redis-backed semantic result cache for RAG chat responses.

The cache key is derived from a normalized query string together with
request parameters that affect the answer (model, reranker, rerank
window). This gives an exact-match cache; a future iteration can add
embedding-similarity eviction or approximate nearest-neighbour keys.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, cast

import redis.asyncio as redis

from shared.config import settings
from shared.logging import get_logger

logger = get_logger(__name__)


def _cache_key(query: str, model: str | None, reranker: str, rerank_top_k: int) -> str:
    """Return a deterministic Redis key for a request signature."""
    normalized = " ".join(query.lower().split())
    payload = f"{normalized}|{model or 'default'}|{reranker}|{rerank_top_k}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"rag:cache:{digest}"


class SemanticCache:
    """Async Redis cache for generated RAG responses."""

    def __init__(
        self,
        redis_url: str | None = None,
        ttl_seconds: int | None = None,
        client: Any | None = None,
    ) -> None:
        """Initialise the cache.

        Args:
            redis_url: Redis connection URL. Defaults to ``settings.redis_url``.
            ttl_seconds: Cache entry TTL. Defaults to
                ``settings.rag_cache_ttl_seconds``.
            client: Optional existing async Redis client.
        """
        self._redis_url = redis_url or settings.redis_url
        self._ttl = ttl_seconds if ttl_seconds is not None else settings.rag_cache_ttl_seconds
        self._client = client

    @property
    def client(self) -> redis.Redis:
        """Lazy async Redis client."""
        if self._client is None:
            self._client = redis.from_url(self._redis_url, decode_responses=True)
        return self._client

    def _key(
        self,
        query: str,
        model: str | None,
        reranker: str,
        rerank_top_k: int,
    ) -> str:
        return _cache_key(query, model, reranker, rerank_top_k)

    async def get(
        self,
        query: str,
        model: str | None,
        reranker: str,
        rerank_top_k: int,
    ) -> dict[str, Any] | None:
        """Return a cached response dict, or ``None``."""
        key = self._key(query, model, reranker, rerank_top_k)
        try:
            raw = await self.client.get(key)
        except Exception as exc:
            logger.warning("cache_get_failed", extra={"error": str(exc)})
            return None

        if raw is None:
            return None

        try:
            return cast(dict[str, Any], json.loads(raw))
        except json.JSONDecodeError as exc:
            logger.warning("cache_decode_failed", extra={"key": key, "error": str(exc)})
            return None

    async def set(
        self,
        query: str,
        model: str | None,
        reranker: str,
        rerank_top_k: int,
        value: dict[str, Any],
    ) -> None:
        """Store a response dict with TTL."""
        key = self._key(query, model, reranker, rerank_top_k)
        try:
            await self.client.set(
                key, json.dumps(value, default=str), ex=self._ttl
            )
        except Exception as exc:
            logger.warning("cache_set_failed", extra={"error": str(exc)})

    async def close(self) -> None:
        """Close the underlying Redis client if owned."""
        if self._client is not None:
            await self._client.close()
            self._client = None
