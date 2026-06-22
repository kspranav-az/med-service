"""Reindex all corpus sources into Qdrant with resume support.

Keeps the embedding model and Qdrant connection loaded across sources
for better performance.

Example:
    uv run reindex-all --parser pymupdf --batch-size 32
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from scripts.indexing import index_source
from shared.corpus_client import load_manifest
from shared.embeddings.embedder import DEFAULT_MODEL, Embedder
from shared.logging import configure_logging, get_logger
from shared.models import Source
from shared.vector_store.qdrant_store import QdrantVectorStore

logger = get_logger(__name__)

PROGRESS_FILE = Path("data/outputs/reindex_progress.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reindex all corpus sources.")
    parser.add_argument(
        "--parser",
        type=str,
        default="pymupdf",
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
    parser.add_argument(
        "--restart",
        action="store_true",
        help="Clear progress and reindex from the beginning.",
    )
    return parser.parse_args()


def load_progress() -> dict[str, list[str]]:
    if PROGRESS_FILE.exists():
        progress: dict[str, list[str]] = json.loads(
            PROGRESS_FILE.read_text(encoding="utf-8")
        )
        return progress
    return {"completed": [], "failed": []}


def save_progress(progress: dict[str, list[str]]) -> None:
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2), encoding="utf-8")


def reindex_source_with_logging(
    source: Source,
    args: argparse.Namespace,
    embedder: Embedder,
    store: QdrantVectorStore,
) -> bool:
    """Index a single source and return True on success."""
    try:
        index_source(
            source=source,
            parser_type=args.parser,
            embedder=embedder,
            store=store,
            batch_size=args.batch_size,
            disable_image_extraction=args.disable_image_extraction,
        )
        return True
    except Exception as exc:  # pragma: no cover
        logger.error(
            "reindex_source_failed",
            extra={"source_id": source.source_id, "error": str(exc)},
        )
        return False


def main() -> None:
    configure_logging()
    args = parse_args()

    if args.restart and PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()
        logger.info("progress_reset")

    progress = load_progress()
    sources = load_manifest()

    logger.info(
        "reindex_all_starting",
        extra={
            "parser": args.parser,
            "total_sources": len(sources),
            "already_completed": len(progress["completed"]),
        },
    )

    start_time = time.perf_counter()

    # Load heavy resources once and reuse across sources.
    embedder = Embedder(model_name=args.embedding_model)
    store = QdrantVectorStore()

    for source in sources:
        if source.source_id in progress["completed"]:
            logger.info(
                "skipping_completed_source",
                extra={"source_id": source.source_id},
            )
            continue

        success = reindex_source_with_logging(source, args, embedder, store)
        if success:
            progress["completed"].append(source.source_id)
            if source.source_id in progress["failed"]:
                progress["failed"].remove(source.source_id)
        else:
            if source.source_id not in progress["failed"]:
                progress["failed"].append(source.source_id)

        save_progress(progress)

    elapsed_seconds = time.perf_counter() - start_time
    elapsed_hours = elapsed_seconds / 3600

    logger.info(
        "reindex_all_complete",
        extra={
            "completed": len(progress["completed"]),
            "failed": len(progress["failed"]),
            "elapsed_seconds": round(elapsed_seconds, 2),
            "elapsed_hours": round(elapsed_hours, 2),
        },
    )
    print(
        f"\n✅ Reindex complete: {len(progress['completed'])}/{len(sources)} sources, "
        f"{len(progress['failed'])} failed, "
        f"elapsed: {elapsed_hours:.2f} hours ({elapsed_seconds:.1f} seconds)"
    )


if __name__ == "__main__":
    main()
