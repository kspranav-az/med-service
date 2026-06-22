"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralised environment-based settings.

    Values are read from ``.env`` files and environment variables.
    All secrets use placeholder defaults for local development only.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Paths
    project_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[1])
    corpus_root: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[1] / "data" / "corpus"
    )

    # Qdrant
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    qdrant_api_key: str | None = Field(default=None, alias="QDRANT_API_KEY")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # RAG caching & deduplication
    rag_cache_ttl_seconds: int = Field(default=3600, alias="RAG_CACHE_TTL_SECONDS")
    rag_dedup_lock_ttl_seconds: int = Field(default=60, alias="RAG_DEDUP_LOCK_TTL_SECONDS")
    rag_dedup_max_wait_seconds: float = Field(default=30.0, alias="RAG_DEDUP_MAX_WAIT_SECONDS")

    # RAG reranker
    rag_default_reranker: str = Field(default="minilm", alias="RAG_DEFAULT_RERANKER")
    rag_reranker_device: str | None = Field(default=None, alias="RAG_RERANKER_DEVICE")
    rag_reranker_batch_size: int = Field(default=16, alias="RAG_RERANKER_BATCH_SIZE")

    # Rate limiting
    rate_limit_autocomplete_requests: int = Field(default=60, alias="RATE_LIMIT_AUTOCOMPLETE_REQUESTS")
    rate_limit_autocomplete_window_seconds: int = Field(default=60, alias="RATE_LIMIT_AUTOCOMPLETE_WINDOW_SECONDS")
    rate_limit_autocomplete_burst: int = Field(default=10, alias="RATE_LIMIT_AUTOCOMPLETE_BURST")
    rate_limit_chat_requests: int = Field(default=10, alias="RATE_LIMIT_CHAT_REQUESTS")
    rate_limit_chat_window_seconds: int = Field(default=60, alias="RATE_LIMIT_CHAT_WINDOW_SECONDS")
    rate_limit_chat_burst: int = Field(default=3, alias="RATE_LIMIT_CHAT_BURST")

    # Langfuse (optional in dev)
    langfuse_public_key: str | None = Field(default=None, alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str | None = Field(default=None, alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(default="https://cloud.langfuse.com", alias="LANGFUSE_HOST")

    # LLM (RAG only)
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_base_url: str = Field(default="https://api.anthropic.com", alias="ANTHROPIC_BASE_URL")
    kimi_api_key: str | None = Field(default=None, alias="KIMI_API_KEY")
    kimi_base_url: str = Field(default="https://api.kimi.com/coding/v1", alias="KIMI_BASE_URL")
    default_llm_model: str = Field(default="claude-sonnet-4-20250514", alias="DEFAULT_LLM_MODEL")

    @property
    def is_development(self) -> bool:
        """Return True when running in a development environment."""
        return self.environment.lower() in {"development", "dev", "local"}

    @property
    def is_production(self) -> bool:
        """Return True when running in a production environment."""
        return self.environment.lower() in {"production", "prod"}


# Singleton-style access. Import this object rather than instantiating Settings repeatedly.
settings = Settings()
