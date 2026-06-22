"""Thin observability wrapper around Langfuse.

Traces are silently dropped when Langfuse is not configured, so local
development works without network calls or credentials.
"""

from __future__ import annotations

import functools
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, TypeVar

from shared.config import settings
from shared.logging import get_logger

logger = get_logger(__name__)

# Optional dependency: Langfuse is part of the ``eval`` extras group.
try:
    from langfuse import Langfuse

    _LANGFUSE_AVAILABLE = True
except ImportError:  # pragma: no cover
    Langfuse = None  # type: ignore[misc, assignment]
    _LANGFUSE_AVAILABLE = False


class _NoOpSpan:
    """Span-like object that ignores all updates and nesting."""

    def __init__(self, span_id: str | None = None) -> None:
        """Initialise with a synthetic id so callers can read ``.id``."""
        self.id = span_id or str(uuid.uuid4())

    def update(self, **kwargs: Any) -> None:  # noqa: ARG002
        """No-op update."""
        return None

    def event(self, **kwargs: Any) -> None:  # noqa: ARG002
        """No-op event."""
        return None

    def span(self, **kwargs: Any) -> _NoOpSpan:  # noqa: ARG002
        """No-op nested span."""
        return _NoOpSpan()


_NO_OP_SPAN = _NoOpSpan()


class ObservabilityClient:
    """Langfuse-backed observability client with graceful no-op fallback."""

    def __init__(self) -> None:
        """Initialise the underlying Langfuse client if credentials are present."""
        self._client: Any | None = None
        self._enabled = bool(
            _LANGFUSE_AVAILABLE and settings.langfuse_public_key and settings.langfuse_secret_key
        )

        if self._enabled and Langfuse is not None:
            try:
                self._client = Langfuse(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key,
                    host=settings.langfuse_host,
                )
                logger.info(
                    "langfuse_client_initialised",
                    extra={"host": settings.langfuse_host},
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("langfuse_init_failed", extra={"error": str(exc)})
                self._enabled = False

    @property
    def is_enabled(self) -> bool:
        """Return True when the client is active and traces will be sent."""
        return self._enabled

    def trace_id(self) -> str:
        """Return a new unique trace identifier string."""
        return str(uuid.uuid4())

    def start_trace(
        self,
        name: str,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Start a new top-level trace.

        Args:
            name: Human-readable trace name.
            metadata: Optional metadata dictionary.
            **kwargs: Additional Langfuse trace parameters.

        Returns:
            A Langfuse trace object or a no-op span with an ``id`` attribute.
        """
        if not self._enabled or self._client is None:
            return _NoOpSpan()

        try:
            trace = self._client.trace(name=name, metadata=metadata, **kwargs)
            return trace if trace is not None else _NoOpSpan()
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "langfuse_trace_failed",
                extra={"name": name, "error": str(exc)},
            )
            return _NoOpSpan()

    @contextmanager
    def trace_span(
        self,
        name: str,
        trace: Any | None = None,
        parent: Any | None = None,
        **kwargs: Any,
    ) -> Iterator[Any]:
        """Context manager for a nested span.

        Args:
            name: Span name.
            trace: Optional parent Langfuse trace object.
            parent: Optional parent span/observation object.
            **kwargs: Additional span attributes.

        Yields:
            A Langfuse span object or a no-op span.
        """
        if not self._enabled or self._client is None:
            yield _NO_OP_SPAN
            return

        span = _NO_OP_SPAN
        try:
            if parent is not None:
                span = parent.span(name=name, **kwargs)
            elif trace is not None:
                span = trace.span(name=name, **kwargs)
            else:
                span = self._client.span(name=name, **kwargs)
            yield span
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "langfuse_span_failed",
                extra={"name": name, "error": str(exc)},
            )
            yield _NO_OP_SPAN
        finally:
            try:
                if span is not _NO_OP_SPAN:
                    span.update()
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "langfuse_span_update_failed",
                    extra={"name": name, "error": str(exc)},
                )


# Global singleton. Services should import this object.
observability = ObservabilityClient()


F = TypeVar("F", bound=Callable[..., Any])


def traced(name: str | None = None) -> Callable[[F], F]:
    """Decorator that wraps a function in a Langfuse span.

    Args:
        name: Optional span name; defaults to the function's qualified name.

    Returns:
        Decorator function.
    """

    def decorator(func: F) -> F:
        span_name = name or f"{func.__module__}.{func.__qualname__}"

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with observability.trace_span(name=span_name):
                return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            with observability.trace_span(name=span_name):
                return await func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return wrapper  # type: ignore[return-value]

    return decorator


# Import here to avoid circular import issues with the decorator.
import asyncio  # noqa: E402
