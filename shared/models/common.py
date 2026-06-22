"""Shared Pydantic models for API contracts and internal data structures."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Source(BaseModel):
    """Metadata about a single document in the corpus."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(..., description="Stable corpus identifier for the document.")
    filename: str = Field(..., description="Original file name.")
    title: str = Field(..., description="Human-readable title.")
    domain: str = Field(..., description="Medical domain or corpus partition.")
    tags: list[str] = Field(default_factory=list, description="Domain tags.")
    path: str = Field(..., description="Relative path within the corpus root.")
    total_pages: int = Field(default=0, ge=0, description="Total pages in the document.")


class Chunk(BaseModel):
    """A text chunk extracted from a corpus document."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(..., description="Globally unique chunk identifier.")
    source_id: str = Field(..., description="Parent document identifier.")
    chunk_index: int = Field(..., ge=0, description="Index of the chunk within the document.")
    page_number: int | None = Field(default=None, ge=1, description="Page number if known.")
    text: str = Field(..., description="Chunk text content.")
    token_count: int | None = Field(default=None, ge=0, description="Approximate token count.")
    metadata: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description="Arbitrary additional metadata.",
    )


class Entity(BaseModel):
    """A medical entity extracted from text.

    ``cui`` and ``tuis`` are nullable to support the SciSpaCy placeholder
    pipeline until a UMLS license is available.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Canonical or surface form of the entity.")
    cui: str | None = Field(
        default=None, description="UMLS Concept Unique Identifier if available."
    )
    tuis: list[str] = Field(
        default_factory=list,
        description="UMLS semantic type identifiers if available.",
    )
    aliases: list[str] = Field(default_factory=list, description="Known synonyms or surface forms.")
    source: str | None = Field(default=None, description="Origin text source identifier.")
    entity_type: str | None = Field(
        default=None,
        description="Provider-specific entity type label (e.g. SciSpaCy label).",
    )


class Citation(BaseModel):
    """A citation linking an answer claim back to a corpus chunk."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(..., description="Referenced chunk identifier.")
    source_id: str = Field(..., description="Parent document identifier.")
    source_title: str | None = Field(default=None, description="Human-readable document title.")
    page: int | None = Field(default=None, ge=1, description="Page number if known.")
    score: float = Field(default=0.0, ge=0.0, le=1.0, description="Retrieval/reranker score.")


class ChatRequest(BaseModel):
    """Request body for the RAG chat endpoint."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1, description="User question.")
    conversation_id: str | None = Field(
        default=None, description="Optional conversation session id."
    )
    model: str | None = Field(default=None, description="LLM model override.")
    top_k: int = Field(default=20, ge=1, le=100, description="Number of chunks to retrieve.")
    rerank_top_k: int = Field(
        default=5, ge=1, le=20, description="Number of chunks after reranking."
    )
    reranker: Literal["minilm", "bge-reranker-v2-m3"] = Field(
        default="minilm",
        description="Reranker tier to use.",
    )
    hybrid_search: bool = Field(
        default=True,
        description="Combine dense vector retrieval with full-text keyword search.",
    )
    require_citations: bool = Field(default=True, description="Return citations with the answer.")
    confidence_threshold: float = Field(default=0.65, ge=0.0, le=1.0)
    max_tokens: int = Field(default=2048, ge=256, le=8192, description="Maximum LLM output tokens.")
    use_cache: bool = Field(default=True, description="Allow cached responses.")


class ChatResponse(BaseModel):
    """Response body for the RAG chat endpoint."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(..., description="Generated answer.")
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_passed: bool = Field(
        default=True,
        description="True when confidence meets or exceeds the request threshold.",
    )
    tokens_used: int | None = Field(default=None, ge=0)
    trace_id: str | None = Field(default=None)
    reranker_used: str | None = Field(default=None)
    cached: bool = Field(default=False)


class AutocompleteRequest(BaseModel):
    """Request body for the semantic autocomplete endpoint."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1, description="Typed prefix or phrase.")
    field_types: str | list[str] = Field(
        default="all",
        description="Semantic type filter: 'all' or list of TUIs.",
    )
    limit: int = Field(default=10, ge=1, le=50)
    fuzzy: bool = Field(default=True, description="Enable fuzzy/typo-tolerant matching.")
    semantic_expansion: bool = Field(
        default=True,
        description="Include vector similarity results.",
    )


class AutocompleteResult(BaseModel):
    """A single autocomplete suggestion."""

    model_config = ConfigDict(extra="forbid")

    term: str = Field(..., description="Display term.")
    cui: str | None = Field(default=None, description="UMLS CUI if available.")
    tuis: list[str] = Field(default_factory=list, description="UMLS TUIs if available.")
    aliases: list[str] = Field(default_factory=list)
    match_type: Literal["prefix", "fuzzy", "semantic", "fusion"] = Field(default="prefix")
    score: float = Field(default=0.0, ge=0.0, le=1.0)


class AutocompleteResponse(BaseModel):
    """Response body for the semantic autocomplete endpoint."""

    model_config = ConfigDict(extra="forbid")

    query: str
    field_types: str | list[str]
    results: list[AutocompleteResult] = Field(default_factory=list)
    latency_ms: float = Field(default=0.0, ge=0.0)
    cached: bool = Field(default=False)
