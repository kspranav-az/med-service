"""FastAPI application entrypoint for the RAG Chat Agent."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from services.rag_chat_agent.api.routes import router
from shared.config import settings
from shared.cors import (
    general_exception_handler,
    get_cors_origins,
    http_exception_handler,
)
from shared.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle."""
    configure_logging()
    logger.info(
        "rag_chat_agent_startup",
        extra={
            "environment": settings.environment,
            "qdrant_url": settings.qdrant_url,
            "redis_url": settings.redis_url,
        },
    )
    yield
    logger.info("rag_chat_agent_shutdown")


app = FastAPI(
    title="MedService RAG Chat Agent",
    description="Retrieval-augmented chat over medical textbook corpus.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)
app.include_router(router, prefix="/api/v1")
