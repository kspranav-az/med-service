"""Shared indexing logic used by reindex scripts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared.chunking import Chunker
from shared.embeddings.embedder import Embedder
from shared.ingestion import ParserType, get_parser
from shared.logging import get_logger
from shared.models import Source
from shared.vector_store.qdrant_store import QdrantVectorStore

logger = get_logger(__name__)

VERSIONS_FILE = Path("data/outputs/source_versions.json")


def load_next_version(source_id: str) -> int:
    """Return the next ingestion version for a source."""
    if VERSIONS_FILE.exists():
        versions: dict[str, int] = json.loads(VERSIONS_FILE.read_text(encoding="utf-8"))
    else:
        versions = {}

    current = versions.get(source_id, 0)
    versions[source_id] = current + 1

    VERSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    VERSIONS_FILE.write_text(json.dumps(versions, indent=2), encoding="utf-8")
    return versions[source_id]


def index_source(
    source: Source,
    parser_type: ParserType | str,
    embedder: Embedder,
    store: QdrantVectorStore,
    batch_size: int = 32,
    disable_image_extraction: bool = True,
) -> int:
    """Parse, chunk, embed, and index a single source.

    Args:
        source: Corpus source to index.
        parser_type: PDF parser backend.
        embedder: Loaded embedding model.
        store: Qdrant vector store client.
        batch_size: Embedding batch size.
        disable_image_extraction: Skip image extraction for Marker parser.

    Returns:
        Number of chunks indexed.
    """
    from shared.corpus_client import resolve_source_path

    pdf_path = resolve_source_path(source)
    if not pdf_path.exists():
        logger.error("pdf_not_found", extra={"source_id": source.source_id, "path": str(pdf_path)})
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    logger.info(
        "indexing_source",
        extra={"source_id": source.source_id, "parser": str(parser_type)},
    )

    parser_kwargs: dict[str, Any] = {}
    if str(parser_type) == ParserType.MARKER:
        parser_kwargs["disable_image_extraction"] = disable_image_extraction

    parser = get_parser(source, parser_type=parser_type, **parser_kwargs)
    pages = parser.parse(pdf_path)

    if not pages:
        logger.warning("no_pages_extracted", extra={"source_id": source.source_id})
        return 0

    chunker = Chunker()
    chunks = chunker.chunk_pages(pages, source_id=source.source_id)

    if not chunks:
        logger.warning("no_chunks_created", extra={"source_id": source.source_id})
        return 0

    texts = [chunk.text for chunk in chunks]
    embeddings = embedder.encode(texts, batch_size=batch_size)

    store.ensure_collection(dimension=embedder.dimension)
    store.delete_by_source(source.source_id)
    version = load_next_version(source.source_id)
    store.upsert_chunks(chunks, embeddings, version=version)

    logger.info(
        "index_source_complete",
        extra={
            "source_id": source.source_id,
            "version": version,
            "chunks": len(chunks),
        },
    )
    return len(chunks)
