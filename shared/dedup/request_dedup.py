"""Distributed request deduplication using Redis locks.

When two clients submit the same query concurrently, only one request
actually computes the answer. The others wait for the result to be
published to a short-lived Redis key, then return it. If the leader
fails or is slow, followers time out and compute the answer themselves.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import redis.asyncio as redis

from shared.config import settings
from shared.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def _signature_key(
    prefix: str,
    query: str,
    model: str | None,
    reranker: str,
    rerank_top_k: int,
) -> str:
    """Return a deterministic Redis key for the request signature."""
    normalized = " ".join(query.lower().split())
    payload = f"{normalized}|{model or 'default'}|{reranker}|{rerank_top_k}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"rag:{prefix}:{digest}"


class RequestDeduplicator:
    """Ensure only one concurrent request computes a given RAG response."""

    def __init__(
        self,
        redis_url: str | None = None,
        lock_ttl_seconds: int | None = None,
        result_ttl_seconds: int | None = None,
        poll_interval: float = 0.25,
        max_wait_seconds: float | None = None,
        client: Any | None = None,
    ) -> None:
        """Initialise the deduplicator.

        Args:
            redis_url: Redis connection URL.
            lock_ttl_seconds: TTL for the leader lock.
            result_ttl_seconds: TTL for the published result.
            poll_interval: How often followers poll for the result.
            max_wait_seconds: Maximum time followers wait before giving up.
            client: Optional existing async Redis client.
        """
        self._redis_url = redis_url or settings.redis_url
        self._lock_ttl = (
            lock_ttl_seconds if lock_ttl_seconds is not None else settings.rag_dedup_lock_ttl_seconds
        )
        self._result_ttl = result_ttl_seconds or self._lock_ttl * 2
        self._poll_interval = poll_interval
        self._max_wait = (
            max_wait_seconds if max_wait_seconds is not None else settings.rag_dedup_max_wait_seconds
        )
        self._client = client

    @property
    def client(self) -> redis.Redis:
        """Lazy async Redis client."""
        if self._client is None:
            self._client = redis.from_url(self._redis_url, decode_responses=True)
        return self._client

    def _lock_key(
        self,
        query: str,
        model: str | None,
        reranker: str,
        rerank_top_k: int,
    ) -> str:
        return _signature_key("lock", query, model, reranker, rerank_top_k)

    def _result_key(
        self,
        query: str,
        model: str | None,
        reranker: str,
        rerank_top_k: int,
    ) -> str:
        return _signature_key("result", query, model, reranker, rerank_top_k)

    async def execute(
        self,
        query: str,
        model: str | None,
        reranker: str,
        rerank_top_k: int,
        factory: Callable[[], Awaitable[T]],
    ) -> T:
        """Run ``factory`` if no other request is computing the same query.

        Args:
            query: Normalised query string.
            model: LLM model identifier.
            reranker: Reranker name.
            rerank_top_k: Number of chunks after reranking.
            factory: Async callable that produces the result.

        Returns:
            The computed result, or a result produced by another request.
        """
        lock_key = self._lock_key(query, model, reranker, rerank_top_k)
        result_key = self._result_key(query, model, reranker, rerank_top_k)

        try:
            acquired = await self.client.set(lock_key, "1", nx=True, ex=self._lock_ttl)
        except Exception as exc:
            logger.warning("dedup_lock_failed", extra={"error": str(exc)})
            return await factory()

        if acquired:
            try:
                result = await factory()
                try:
                    await self.client.setex(
                        result_key,
                        self._result_ttl,
                        json.dumps(result, default=str),
                    )
                except Exception as exc:
                    logger.warning("dedup_result_publish_failed", extra={"error": str(exc)})
                return result
            finally:
                try:
                    await self.client.delete(lock_key)
                except Exception as exc:
                    logger.warning("dedup_unlock_failed", extra={"error": str(exc)})

        # Another request holds the lock; wait for the result.
        waited = 0.0
        while waited < self._max_wait:
            try:
                raw = await self.client.get(result_key)
                if raw:
                    return json.loads(raw)  # type: ignore[no-any-return]
            except Exception:
                pass

            await asyncio.sleep(self._poll_interval)
            waited += self._poll_interval

        logger.warning("dedup_wait_timeout", extra={"lock_key": lock_key})
        return await factory()
