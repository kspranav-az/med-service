"""Token-bucket rate limiter backed by Redis.

The limiter is async and uses a Lua script to keep the bucket state
atomic across concurrent requests.
"""

from __future__ import annotations

import time

import redis.asyncio as redis

from shared.config import settings
from shared.logging import get_logger

logger = get_logger(__name__)

# Token bucket Lua script.
# Args: burst, rate, window_seconds, now, requested
token_bucket_script = """
local key = KEYS[1]
local burst = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local window = tonumber(ARGV[3])
local now = tonumber(ARGV[4])
local requested = tonumber(ARGV[5])

local fill_per_sec = rate / window
local state = redis.call('HMGET', key, 'tokens', 'updated_at')
local tokens = tonumber(state[1])
local updated_at = tonumber(state[2])

if tokens == nil then
    tokens = burst
    updated_at = now
end

local elapsed = now - updated_at
tokens = math.min(burst, tokens + elapsed * fill_per_sec)

if tokens >= requested then
    tokens = tokens - requested
    redis.call('HMSET', key, 'tokens', tokens, 'updated_at', now)
    redis.call('EXPIRE', key, math.ceil(window * 2))
    return {1, math.floor(tokens)}
else
    redis.call('HMSET', key, 'tokens', tokens, 'updated_at', now)
    redis.call('EXPIRE', key, math.ceil(window * 2))
    return {0, math.floor(tokens)}
end
"""


class RateLimitExceededError(Exception):
    """Raised when a request exceeds the configured rate limit."""

    def __init__(self, retry_after: int) -> None:
        """Initialise with seconds until the next allowed request."""
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded; retry after {retry_after}s")


class RateLimiter:
    """Redis-backed token-bucket rate limiter."""

    def __init__(
        self,
        key_prefix: str,
        max_requests: int,
        window_seconds: int,
        burst: int,
        redis_url: str | None = None,
        client: redis.Redis | None = None,
    ) -> None:
        """Initialise the limiter.

        Args:
            key_prefix: Redis key prefix (e.g. ``rl:chat``).
            max_requests: Maximum requests allowed per window.
            window_seconds: Length of the rate-limit window.
            burst: Maximum requests allowed in a short burst.
            redis_url: Redis connection URL.
            client: Optional existing async Redis client.
        """
        self.key_prefix = key_prefix
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.burst = burst
        self._redis_url = redis_url or settings.redis_url
        self._client = client
        self._script_sha: str | None = None

    @property
    def client(self) -> redis.Redis:
        """Lazy async Redis client."""
        if self._client is None:
            self._client = redis.from_url(self._redis_url, decode_responses=True)
        return self._client

    def _key(self, identifier: str) -> str:
        return f"{self.key_prefix}:{identifier}"

    async def is_allowed(self, identifier: str, requested: int = 1) -> tuple[bool, int, int]:
        """Check whether ``identifier`` may make ``requested`` requests.

        Args:
            identifier: Unique client identifier (typically IP address).
            requested: Number of requests to consume (default 1).

        Returns:
            Tuple of ``(allowed, remaining, retry_after)``.
        """
        key = self._key(identifier)
        now = time.time()

        if self._script_sha is None:
            self._script_sha = await self.client.script_load(token_bucket_script)

        try:
            result = await self.client.evalsha(
                self._script_sha,
                1,
                key,
                self.burst,
                self.max_requests,
                self.window_seconds,
                now,
                requested,
            )
        except Exception as exc:  # pragma: no cover
            if "NOSCRIPT" not in str(exc):
                raise
            self._script_sha = await self.client.script_load(token_bucket_script)
            result = await self.client.evalsha(
                self._script_sha,
                1,
                key,
                self.burst,
                self.max_requests,
                self.window_seconds,
                now,
                requested,
            )

        allowed = bool(result[0])
        remaining = int(result[1])
        retry_after = self.window_seconds if not allowed else 0
        return allowed, remaining, retry_after

    async def check(self, identifier: str) -> tuple[int, int]:
        """Check rate limit and raise if exceeded.

        Args:
            identifier: Unique client identifier.

        Returns:
            Tuple of ``(remaining, retry_after)`` when allowed.

        Raises:
            RateLimitExceeded: If the identifier has exceeded the limit.
        """
        allowed, remaining, retry_after = await self.is_allowed(identifier)
        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                extra={
                    "key_prefix": self.key_prefix,
                    "identifier": identifier,
                    "retry_after": retry_after,
                },
            )
            raise RateLimitExceededError(retry_after)
        return remaining, retry_after

    @classmethod
    def for_autocomplete(cls, client: redis.Redis | None = None) -> RateLimiter:
        """Return the configured autocomplete rate limiter."""
        return cls(
            key_prefix="rl:autocomplete",
            max_requests=settings.rate_limit_autocomplete_requests,
            window_seconds=settings.rate_limit_autocomplete_window_seconds,
            burst=settings.rate_limit_autocomplete_burst,
            client=client,
        )

    @classmethod
    def for_chat(cls, client: redis.Redis | None = None) -> RateLimiter:
        """Return the configured chat rate limiter."""
        return cls(
            key_prefix="rl:chat",
            max_requests=settings.rate_limit_chat_requests,
            window_seconds=settings.rate_limit_chat_window_seconds,
            burst=settings.rate_limit_chat_burst,
            client=client,
        )
