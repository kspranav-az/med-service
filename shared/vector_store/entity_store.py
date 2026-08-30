"""Qdrant vector store for medical entity embeddings."""

from __future__ import annotations

import uuid
from typing import Any

from numpy.typing import NDArray
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchText,
    PayloadSchemaType,
    PointStruct,
    QueryResponse,
    ScalarQuantization,
    ScalarQuantizationConfig,
    ScalarType,
    VectorParams,
)

from shared.config import settings
from shared.logging import get_logger
from shared.models import Entity

logger = get_logger(__name__)

ENTITIES_COLLECTION = "entities"


def _entity_id(entity: Entity) -> str:
    """Return a deterministic UUID for an entity based on name + types."""
    key = f"{entity.name.lower()}:{','.join(sorted(entity.tuis or []))}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, key))


class EntityVectorStore:
    """Client for storing and searching entity embeddings in Qdrant."""

    def __init__(
        self,
        collection_name: str = ENTITIES_COLLECTION,
        client: QdrantClient | None = None,
    ) -> None:
        """Initialise the entity vector store.

        Args:
            collection_name: Name of the Qdrant collection.
            client: Optional QdrantClient instance.
        """
        self.collection_name = collection_name
        self.client = client or QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            check_compatibility=False,
            timeout=120,
        )

    def ensure_collection(self, dimension: int = 768) -> None:
        """Create the entities collection if it does not exist."""
        exists = self.client.collection_exists(self.collection_name)
        if exists:
            logger.info("collection_exists", extra={"collection": self.collection_name})
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=dimension,
                distance=Distance.COSINE,
            ),
            quantization_config=ScalarQuantization(
                scalar=ScalarQuantizationConfig(type=ScalarType.INT8, always_ram=False),
            ),
        )

        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="term",
            field_schema=PayloadSchemaType.TEXT,
        )
        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="tuis",
            field_schema=PayloadSchemaType.KEYWORD,
        )

        logger.info(
            "collection_created",
            extra={"collection": self.collection_name, "dimension": dimension},
        )

    def upsert_entities(
        self,
        entities: list[Entity],
        embeddings: NDArray[Any],
        upsert_batch_size: int = 250,
        wait: bool = True,
    ) -> None:
        """Insert or update entity vectors in batches.

        Args:
            entities: Entities to store.
            embeddings: Normalised embedding vectors of shape (n_entities, dimension).
            upsert_batch_size: Number of points to send per Qdrant upsert request.
            wait: Whether to wait for each batch to be persisted. Use ``False``
                for large bulk inserts to avoid client timeouts.
        """
        if len(entities) != len(embeddings):
            raise ValueError("entities and embeddings must have the same length")

        points: list[PointStruct] = []
        for idx, entity in enumerate(entities):
            points.append(
                PointStruct(
                    id=_entity_id(entity),
                    vector=embeddings[idx].tolist(),
                    payload={
                        "entity_id": _entity_id(entity),
                        "term": entity.name,
                        "aliases": entity.aliases,
                        "tuis": entity.tuis,
                        "cui": entity.cui,
                        "source_id": entity.source,
                    },
                )
            )

        total_upserted = 0
        for i in range(0, len(points), upsert_batch_size):
            batch = points[i : i + upsert_batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
                wait=wait,
            )
            total_upserted += len(batch)

        logger.info(
            "entities_upserted",
            extra={
                "collection": self.collection_name,
                "count": total_upserted,
                "batches": (len(points) + upsert_batch_size - 1) // upsert_batch_size,
            },
        )

    def search(
        self,
        query_embedding: list[float] | NDArray[Any],
        top_k: int = 20,
        tuis: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for semantically similar entities.

        Args:
            query_embedding: Query vector.
            top_k: Number of results.
            tuis: Optional list of internal TUI filters.

        Returns:
            List of result dicts with ``id``, ``score``, and ``payload``.
        """
        from qdrant_client.models import FieldCondition, Filter, MatchAny

        search_filter = None
        if tuis:
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="tuis",
                        match=MatchAny(any=tuis),
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

        return [
            {
                "id": point.id,
                "score": point.score,
                "payload": point.payload,
            }
            for point in response.points
        ]

    def delete_by_term(self, term: str) -> int:
        """Delete entities matching a term via full-text payload filter.

        Args:
            term: Entity term to delete.

        Returns:
            Number of deleted points.
        """
        result = self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="term",
                        match=MatchText(text=term),
                    )
                ]
            ),
        )
        deleted = result.operation_id if result and result.operation_id is not None else 0
        logger.info(
            "entities_deleted_by_term",
            extra={"collection": self.collection_name, "term": term, "deleted": deleted},
        )
        return deleted

    def count(self) -> int:
        """Return the total number of entities in the collection."""
        return self.client.count(collection_name=self.collection_name).count
