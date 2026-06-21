"""Parse, chunk, embed, and index a single source into Qdrant.

Example:
    uv run python scripts/reindex_source.py --source urodynamics_iaps --parser pymupdf
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shared.chunking import Chunker
from shared.corpus_client import get_source_by_id, resolve_source_path
from shared.embeddings.embedder import DEFAULT_MODEL, Embedder
from shared.ingestion import ParserType, get_parser
from shared.logging import configure_logging, get_logger
from shared.vector_store.qdrant_store import QdrantVectorStore

logger = get_logger(__name__)

VERSIONS_FILE = Path("data/outputs/source_versions.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reindex a single corpus source.")
    parser.add_argument(
        "--source",
        type=str,
        required=True,
        help="Source id to reindex.",
    )
    parser.add_argument(
        "--parser",
        type=str,
        default=ParserType.PYMUPDF,
        choices=[p.value for p in ParserType],
        help="PDF parser backend.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Embedding batch size.",
    )
    parser.add_argument(
        "--disable-image-extraction",
        action="store_true",
        help="Disable image extraction for Marker parser.",
    )
    parser.add_argument(
        "--embedding-model",
        type=str,
        default=DEFAULT_MODEL,
        help="Sentence-transformers model name.",
    )
    return parser.parse_args()


def load_next_version(source_id: str) -> int:
    """Return the next ingestion version for a source."""
    if VERSIONS_FILE.exists():
        versions = json.loads(VERSIONS_FILE.read_text(encoding="utf-8"))
    else:
        versions = {}

    current = versions.get(source_id, 0)
    versions[source_id] = current + 1

    VERSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    VERSIONS_FILE.write_text(json.dumps(versions, indent=2), encoding="utf-8")
    return versions[source_id]


def main() -> None:
    configure_logging()
    args = parse_args()

    source = get_source_by_id(args.source)
    if source is None:
        logger.error("source_not_found", extra={"source_id": args.source})
        raise SystemExit(1)

    pdf_path = resolve_source_path(source)
    if not pdf_path.exists():
        logger.error("pdf_not_found", extra={"source_id": source.source_id, "path": str(pdf_path)})
        raise SystemExit(1)

    logger.info(
        "reindexing_source",
        extra={"source_id": source.source_id, "parser": args.parser},
    )

    # 1. Parse
    parser_kwargs = {}
    if args.parser == ParserType.MARKER:
        parser_kwargs["disable_image_extraction"] = args.disable_image_extraction
    parser = get_parser(source, parser_type=args.parser, **parser_kwargs)
    pages = parser.parse(pdf_path)

    if not pages:
        logger.warning("no_pages_extracted", extra={"source_id": source.source_id})
        return

    # 2. Chunk
    chunker = Chunker()
    chunks = chunker.chunk_pages(pages, source_id=source.source_id)

    if not chunks:
        logger.warning("no_chunks_created", extra={"source_id": source.source_id})
        return

    # 3. Embed
    embedder = Embedder(model_name=args.embedding_model)
    texts = [chunk.text for chunk in chunks]
    embeddings = embedder.encode(texts, batch_size=args.batch_size)

    # 4. Index
    store = QdrantVectorStore()
    store.ensure_collection(dimension=embedder.dimension)
    store.delete_by_source(source.source_id)
    version = load_next_version(source.source_id)
    store.upsert_chunks(chunks, embeddings, version=version)

    logger.info(
        "reindex_complete",
        extra={
            "source_id": source.source_id,
            "version": version,
            "chunks": len(chunks),
        },
    )


if __name__ == "__main__":
    main()
