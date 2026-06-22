"""Embed extracted entities and index them in Qdrant."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shared.config import settings
from shared.embeddings.embedder import Embedder
from shared.logging import configure_logging, get_logger
from shared.models import Entity
from shared.vector_store.entity_store import EntityVectorStore

logger = get_logger(__name__)

DEFAULT_ENTITY_FILE = settings.project_root / "data" / "processed" / "entities" / "scispacy_entities.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Embed extracted entities and index them in Qdrant.")
    parser.add_argument(
        "--entity-file",
        type=Path,
        default=None,
        help="Path to scispacy_entities.json. Defaults to data/processed/entities/scispacy_entities.json.",
    )
    return parser.parse_args()


def main(entity_file: Path | str | None = None) -> None:
    """Read entities from JSON, embed them, and upsert into Qdrant.

    Args:
        entity_file: Path to ``scispacy_entities.json``.
    """
    configure_logging()

    if entity_file is None:
        args = _parse_args()
        entity_file = args.entity_file

    entity_file = Path(entity_file or DEFAULT_ENTITY_FILE)
    if not entity_file.exists():
        raise FileNotFoundError(
            f"Entity file not found: {entity_file}. "
            "Run `uv run extract-entities` first."
        )

    raw_records = json.loads(entity_file.read_text(encoding="utf-8"))
    entities = [
        Entity.model_validate(record)
        for record in raw_records
    ]

    if not entities:
        logger.warning("no_entities_to_index", extra={"path": str(entity_file)})
        return

    logger.info("embedding_entities", extra={"count": len(entities)})
    embedder = Embedder()
    texts = [entity.name for entity in entities]
    embeddings = embedder.encode(texts, batch_size=64, show_progress=True)

    store = EntityVectorStore()
    store.ensure_collection(dimension=embedder.dimension)
    store.upsert_entities(entities, embeddings)

    logger.info(
        "entities_indexed",
        extra={
            "count": len(entities),
            "collection": store.collection_name,
        },
    )


if __name__ == "__main__":
    main()
