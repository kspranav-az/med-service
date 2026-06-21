"""FastAPI application entrypoint for the Semantic Autocomplete service."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from services.autocomplete.api.routes import router
from shared.config import settings
from shared.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle."""
    configure_logging()
    logger.info(
        "autocomplete_startup",
        extra={
            "environment": settings.environment,
            "redis_url": settings.redis_url,
        },
    )
    yield
    logger.info("autocomplete_shutdown")


app = FastAPI(
    title="MedService Semantic Autocomplete",
    description="Medical semantic autocomplete backed by trie and vector search.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router, prefix="/api/v1")
