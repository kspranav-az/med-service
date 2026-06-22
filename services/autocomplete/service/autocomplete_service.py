"""Semantic autocomplete service over medical entities."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import redis.asyncio as redis

from services.autocomplete.service.trie import EntityTrie
from shared.config import settings
from shared.embeddings.embedder import DEFAULT_MODEL, Embedder
from shared.fusion.rrf import reciprocal_rank_fusion
from shared.fuzzy.fuzzy_matcher import FuzzyMatcher
from shared.logging import get_logger
from shared.models import AutocompleteRequest, AutocompleteResponse, AutocompleteResult, Entity
from shared.vector_store.entity_store import EntityVectorStore

logger = get_logger(__name__)

DEFAULT_CACHE_TTL_SECONDS = 24 * 60 * 60


def _default_entity_file() -> Path:
    """Return the default entity JSON path based on current settings."""
    return settings.project_root / "data" / "processed" / "entities" / "scispacy_entities.json"


def _normalise_field_types(field_types: str | list[str]) -> list[str]:
    """Return a list of TUIs or an empty list for ``all``."""
    if isinstance(field_types, str):
        return [] if field_types.lower() == "all" else [field_types]
    return field_types


def _cache_key(query: str, field_types: list[str], fuzzy: bool, semantic: bool, limit: int) -> str:
    payload = "|".join([
        " ".join(query.lower().split()),
        ",".join(sorted(field_types)),
        str(fuzzy),
        str(semantic),
        str(limit),
    ])
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"ac:{digest}"


class AutocompleteCache:
    """Redis cache for autocomplete results."""

    def __init__(
        self,
        redis_url: str | None = None,
        ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        client: redis.Redis | None = None,
    ) -> None:
        self._redis_url = redis_url or settings.redis_url
        self._ttl = ttl_seconds
        self._client = client

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(self._redis_url, decode_responses=True)
        return self._client

    async def get(
        self,
        query: str,
        field_types: list[str],
        fuzzy: bool,
        semantic: bool,
        limit: int,
    ) -> dict[str, Any] | None:
        key = _cache_key(query, field_types, fuzzy, semantic, limit)
        try:
            raw = await self.client.get(key)
            return json.loads(raw) if raw else None
        except Exception as exc:
            logger.warning("autocomplete_cache_get_failed", extra={"error": str(exc)})
            return None

    async def set(
        self,
        query: str,
        field_types: list[str],
        fuzzy: bool,
        semantic: bool,
        limit: int,
        value: dict[str, Any],
    ) -> None:
        key = _cache_key(query, field_types, fuzzy, semantic, limit)
        try:
            await self.client.setex(key, self._ttl, json.dumps(value, default=str))
        except Exception as exc:
            logger.warning("autocomplete_cache_set_failed", extra={"error": str(exc)})


class AutocompleteService:
    """Autocomplete over entities using prefix, fuzzy, and semantic matching."""

    def __init__(
        self,
        entity_file: Path | str | None = None,
        embedder: Embedder | None = None,
        vector_store: EntityVectorStore | None = None,
        cache: AutocompleteCache | None = None,
    ) -> None:
        """Initialise and build the autocomplete index.

        Args:
            entity_file: Path to the extracted entities JSON file.
            embedder: Embedding model for semantic search.
            vector_store: Qdrant entity vector store.
            cache: Redis autocomplete cache.
        """
        self._entity_file = Path(entity_file or _default_entity_file())
        self._embedder = embedder
        self._vector_store = vector_store or EntityVectorStore()
        self._cache = cache or AutocompleteCache()

        self._entities: list[Entity] = []
        self._trie = EntityTrie()
        self._fuzzy: FuzzyMatcher | None = None
        self._build_index()

    @property
    def embedder(self) -> Embedder:
        """Lazy-load the embedding model."""
        if self._embedder is None:
            self._embedder = Embedder(model_name=DEFAULT_MODEL)
        return self._embedder

    def _build_index(self) -> None:
        """Load entities from JSON and build the trie and fuzzy matcher."""
        if not self._entity_file.exists():
            logger.warning(
                "entity_file_not_found",
                extra={"path": str(self._entity_file)},
            )
            return

        try:
            raw = json.loads(self._entity_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.error("entity_file_decode_failed", extra={"error": str(exc)})
            return

        candidates: list[tuple[str, Entity]] = []
        for record in raw:
            try:
                entity = Entity.model_validate(record)
            except Exception:
                continue

            self._entities.append(entity)
            term = entity.name.strip()
            if term:
                self._trie.insert(term, entity)
                candidates.append((term, entity))
            for alias in entity.aliases:
                alias = alias.strip()
                if alias and alias.lower() != term.lower():
                    self._trie.insert(alias, entity)
                    candidates.append((alias, entity))

        if candidates:
            self._fuzzy = FuzzyMatcher(candidates)

        logger.info(
            "autocomplete_index_built",
            extra={
                "entities": len(self._entities),
                "terms": len(candidates),
                "path": str(self._entity_file),
            },
        )

    def _filter_by_type(
        self,
        results: list[tuple[Entity, float]],
        field_types: list[str],
    ) -> list[tuple[Entity, float]]:
        """Keep only entities whose TUIs intersect with ``field_types``."""
        if not field_types:
            return results

        allowed = {ft.lower() for ft in field_types}
        filtered: list[tuple[Entity, float]] = []
        for entity, score in results:
            entity_types = {tui.lower() for tui in (entity.tuis or [])}
            if entity_types & allowed:
                filtered.append((entity, score))
        return filtered

    def _to_results(
        self,
        fused: list[tuple[Entity, float]],
        limit: int,
    ) -> list[AutocompleteResult]:
        """Convert fused entities to AutocompleteResult objects."""
        max_score = fused[0][1] if fused else 1.0
        return [
            AutocompleteResult(
                term=entity.name,
                cui=entity.cui,
                tuis=entity.tuis,
                aliases=entity.aliases,
                match_type="fusion",
                score=round(min(score / max_score, 1.0), 4) if max_score else 0.0,
            )
            for entity, score in fused[:limit]
        ]

    async def _semantic_search(
        self,
        query: str,
        limit: int,
        field_types: list[str],
    ) -> list[Entity]:
        """Return entities semantically similar to ``query``."""
        try:
            embeddings = self.embedder.encode([query], show_progress=False)
            results = self._vector_store.search(
                query_embedding=embeddings[0],
                top_k=limit,
                tuis=field_types or None,
            )
            entities: list[Entity] = []
            for hit in results:
                payload = hit.get("payload", {})
                try:
                    entity = Entity(
                        name=payload.get("term", ""),
                        cui=payload.get("cui"),
                        tuis=payload.get("tuis", []),
                        aliases=payload.get("aliases", []),
                        source=payload.get("source_id"),
                        entity_type=None,
                    )
                    entities.append(entity)
                except Exception:
                    continue
            return entities
        except Exception as exc:
            logger.warning("semantic_search_failed", extra={"error": str(exc)})
            return []

    async def complete(self, request: AutocompleteRequest) -> AutocompleteResponse:
        """Return autocomplete suggestions for the request."""
        query = request.query.strip()
        field_types = _normalise_field_types(request.field_types)
        fuzzy = request.fuzzy
        semantic = request.semantic_expansion
        limit = request.limit

        cached = await self._cache.get(query, field_types, fuzzy, semantic, limit)
        if cached is not None:
            return AutocompleteResponse.model_validate({**cached, "cached": True})

        start_time = __import__("time").time()

        result_lists: list[list[Entity]] = []

        prefix_results = self._trie.prefix_search(query, limit=limit * 2)
        if prefix_results:
            result_lists.append(prefix_results)

        if fuzzy and self._fuzzy is not None:
            fuzzy_hits: list[tuple[Entity, float]] = self._fuzzy.search(
                query, limit=limit * 2, score_cutoff=75
            )
            if fuzzy_hits:
                result_lists.append([entity for entity, _score in fuzzy_hits])

        if semantic:
            semantic_results = await self._semantic_search(
                query,
                limit=limit * 2,
                field_types=field_types,
            )
            if semantic_results:
                result_lists.append(semantic_results)

        if not result_lists:
            return AutocompleteResponse(
                query=query,
                field_types=request.field_types,
                results=[],
                latency_ms=0.0,
            )

        fused = reciprocal_rank_fusion(
            result_lists,
            key_func=lambda e: f"{e.name.lower()}:{','.join(sorted(e.tuis or []))}",
            top_k=limit * 2,
        )
        filtered = self._filter_by_type(fused, field_types)
        results = self._to_results(filtered, limit)

        latency_ms = round((__import__("time").time() - start_time) * 1000, 2)

        response = AutocompleteResponse(
            query=query,
            field_types=request.field_types,
            results=results,
            latency_ms=latency_ms,
        )

        await self._cache.set(
            query,
            field_types,
            fuzzy,
            semantic,
            limit,
            value=response.model_dump(mode="json"),
        )

        return response
