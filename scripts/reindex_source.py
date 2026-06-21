"""Parse, chunk, embed, and index a single source into Qdrant.

Example:
    uv run reindex-source --source urodynamics_iaps --parser pymupdf
"""

from __future__ import annotations

import argparse

from scripts.indexing import index_source
from shared.corpus_client import get_source_by_id
from shared.embeddings.embedder import DEFAULT_MODEL, Embedder
from shared.ingestion import ParserType
from shared.logging import configure_logging, get_logger
from shared.vector_store.qdrant_store import QdrantVectorStore

logger = get_logger(__name__)


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


def main() -> None:
    configure_logging()
    args = parse_args()

    source = get_source_by_id(args.source)
    if source is None:
        logger.error("source_not_found", extra={"source_id": args.source})
        raise SystemExit(1)

    embedder = Embedder(model_name=args.embedding_model)
    store = QdrantVectorStore()

    index_source(
        source=source,
        parser_type=args.parser,
        embedder=embedder,
        store=store,
        batch_size=args.batch_size,
        disable_image_extraction=args.disable_image_extraction,
    )


if __name__ == "__main__":
    main()
