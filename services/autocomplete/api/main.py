"""FastAPI application entrypoint for the Semantic Autocomplete service."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from services.autocomplete.api.routes import _get_service, router
from shared.config import settings
from shared.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle."""
    configure_logging()
    logger.info(
        "autocomplete_startup",
        extra={
            "environment": settings.environment,
            "redis_url": settings.redis_url,
        },
    )
    # Build the trie and load the embedding model before accepting traffic.
    await asyncio.to_thread(_get_service)
    logger.info("autocomplete_index_warmed")
    yield
    logger.info("autocomplete_shutdown")


app = FastAPI(
    title="MedService Semantic Autocomplete",
    description="Medical semantic autocomplete backed by trie and vector search.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router, prefix="/api/v1")
