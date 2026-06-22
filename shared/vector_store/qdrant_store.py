"""Qdrant vector store client for RAG chunks."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from numpy.typing import NDArray
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchText,
    MatchValue,
    PayloadSchemaType,
    PointIdsList,
    PointStruct,
    QueryResponse,
    ScalarQuantization,
    ScalarQuantizationConfig,
    VectorParams,
)

from shared.config import settings
from shared.logging import get_logger
from shared.models import Chunk

logger = get_logger(__name__)

DEFAULT_COLLECTION = "rag_chunks"


def _point_id(chunk_id: str) -> str:
    """Return a deterministic UUID string for a chunk ID.

    Qdrant requires point IDs to be either unsigned integers or UUIDs.
    We keep the human-readable ``chunk_id`` in the payload and use a
    UUID derived from it as the Qdrant point ID.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))


class QdrantVectorStore:
    """Client for storing and searching RAG chunk embeddings in Qdrant."""

    def __init__(
        self,
        collection_name: str = DEFAULT_COLLECTION,
        client: QdrantClient | None = None,
    ) -> None:
        """Initialise the vector store.

        Args:
            collection_name: Name of the Qdrant collection.
            client: Optional QdrantClient instance.
        """
        self.collection_name = collection_name
        self.client = client or QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            check_compatibility=False,
        )

    def ensure_collection(self, dimension: int = 768) -> None:
        """Create the collection if it does not exist.

        Args:
            dimension: Embedding vector dimension.
        """
        exists = self.client.collection_exists(self.collection_name)
        if exists:
            logger.info(
                "collection_exists",
                extra={"collection": self.collection_name},
            )
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=dimension,
                distance=Distance.COSINE,
            ),
            quantization_config=ScalarQuantization(
                scalar=ScalarQuantizationConfig(type="int8", always_ram=False),
            ),
        )

        # Payload indexes for efficient filtering.
        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="source_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="page_number",
            field_schema=PayloadSchemaType.INTEGER,
        )
        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="chunk_index",
            field_schema=PayloadSchemaType.INTEGER,
        )
        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="text",
            field_schema=PayloadSchemaType.TEXT,
        )

        logger.info(
            "collection_created",
            extra={"collection": self.collection_name, "dimension": dimension},
        )

    def upsert_chunks(
        self,
        chunks: list[Chunk],
        embeddings: NDArray[Any],
        version: int = 1,
        upsert_batch_size: int = 500,
    ) -> None:
        """Insert or update chunks in the collection.

        Args:
            chunks: Chunks to upsert.
            embeddings: Normalized embedding vectors of shape (n_chunks, dimension).
            version: Ingestion version number for the source.
            upsert_batch_size: Number of points to send per Qdrant upsert request.
        """
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")

        ingest_date = datetime.now(UTC).isoformat()
        points: list[PointStruct] = []

        for idx, chunk in enumerate(chunks):
            points.append(
                PointStruct(
                    id=_point_id(chunk.chunk_id),
                    vector=embeddings[idx].tolist(),
                    payload={
                        "chunk_id": chunk.chunk_id,
                        "source_id": chunk.source_id,
                        "chunk_index": chunk.chunk_index,
                        "page_number": chunk.page_number,
                        "text": chunk.text,
                        "token_count": chunk.token_count,
                        "version": version,
                        "ingest_date": ingest_date,
                        **chunk.metadata,
                    },
                )
            )

        total_upserted = 0
        for i in range(0, len(points), upsert_batch_size):
            batch = points[i : i + upsert_batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
                wait=True,
            )
            total_upserted += len(batch)

        logger.info(
            "chunks_upserted",
            extra={
                "collection": self.collection_name,
                "source_id": chunks[0].source_id if chunks else None,
                "count": total_upserted,
                "version": version,
            },
        )

    def delete_by_source(self, source_id: str) -> int:
        """Delete all chunks belonging to a source.

        Args:
            source_id: Source identifier.

        Returns:
            Number of deleted points.
        """
        result = self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="source_id",
                        match=MatchValue(value=source_id),
                    )
                ]
            ),
        )
        deleted = result.operation_id if result else 0
        logger.info(
            "chunks_deleted_by_source",
            extra={"collection": self.collection_name, "source_id": source_id, "deleted": deleted},
        )
        return deleted

    def delete_by_chunk_ids(self, chunk_ids: list[str]) -> None:
        """Delete specific chunks by their IDs."""
        if not chunk_ids:
            return

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=PointIdsList(points=[_point_id(cid) for cid in chunk_ids]),
        )

    def _ensure_text_index(self) -> None:
        """Create a full-text payload index on ``text`` if it does not exist."""
        info = self.client.get_collection(self.collection_name)
        schema = getattr(info, "payload_schema", {}) or {}
        if "text" in schema:
            return

        try:
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="text",
                field_schema=PayloadSchemaType.TEXT,
            )
            logger.info("text_index_created", extra={"collection": self.collection_name})
        except Exception as exc:  # pragma: no cover
            logger.warning("text_index_creation_failed", extra={"error": str(exc)})

    def keyword_search(
        self,
        query: str,
        top_k: int = 20,
        source_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Full-text keyword search over chunk text payloads.

        Args:
            query: Keyword query.
            top_k: Maximum number of keyword matches.
            source_id: Optional source filter.

        Returns:
            List of result dicts. Scores are set to 0.0 because Qdrant
            full-text filtering does not return a relevance score; ranks
            are used for fusion.
        """
        self._ensure_text_index()

        conditions: list[Any] = [
            FieldCondition(key="text", match=MatchText(text=query)),
        ]
        if source_id:
            conditions.append(
                FieldCondition(key="source_id", match=MatchValue(value=source_id)),
            )

        response: QueryResponse = self.client.query_points(
            collection_name=self.collection_name,
            query_filter=Filter(must=conditions),
            limit=top_k,
            with_payload=True,
        )

        return [
            {
                "id": point.id,
                "score": 0.0,
                "payload": point.payload,
            }
            for point in response.points
        ]

    def search(
        self,
        query_embedding: list[float] | NDArray[Any],
        top_k: int = 20,
        source_id: str | None = None,
        keyword_query: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for nearest chunks, optionally fusing with keyword search.

        Args:
            query_embedding: Query vector.
            top_k: Number of results.
            source_id: Optional source filter.
            keyword_query: If provided, run a full-text keyword search and
                fuse dense + keyword results with reciprocal rank fusion.

        Returns:
            List of result dicts with ``id``, ``score``, and ``payload``.
        """
        search_filter = None
        if source_id:
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="source_id",
                        match=MatchValue(value=source_id),
                    )
                ]
            )

        query_vector = (
            query_embedding.tolist() if hasattr(query_embedding, "tolist") else query_embedding
        )

        response: QueryResponse = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=search_filter,
            limit=top_k,
            with_payload=True,
        )

        dense_results = [
            {
                "id": point.id,
                "score": point.score,
                "payload": point.payload,
            }
            for point in response.points
        ]

        if not keyword_query:
            return dense_results

        keyword_results = self.keyword_search(
            query=keyword_query,
            top_k=top_k,
            source_id=source_id,
        )

        return _fuse_results(dense_results, keyword_results, top_k=top_k)

    def count(self) -> int:
        """Return the total number of points in the collection."""
        return self.client.count(collection_name=self.collection_name).count


def _fuse_results(
    dense_results: list[dict[str, Any]],
    keyword_results: list[dict[str, Any]],
    top_k: int,
    k: int = 60,
) -> list[dict[str, Any]]:
    """Fuse dense and keyword result lists with reciprocal rank fusion.

    Args:
        dense_results: Dense vector search results.
        keyword_results: Keyword search results.
        top_k: Number of fused results to return.
        k: RRF ranking constant.

    Returns:
        Fused results sorted by RRF score.
    """
    scores: dict[Any, float] = {}
    items: dict[Any, dict[str, Any]] = {}

    for rank, hit in enumerate(dense_results):
        key = hit["id"]
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        items[key] = hit

    for rank, hit in enumerate(keyword_results):
        key = hit["id"]
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        items[key] = hit

    sorted_keys = sorted(scores, key=scores.get, reverse=True)  # type: ignore[arg-type]
    return [
        {**items[key], "score": round(scores[key], 4)}
        for key in sorted_keys[:top_k]
    ]
