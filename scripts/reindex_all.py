"""Reindex all corpus sources into Qdrant with resume support.

Example:
    uv run python scripts/reindex_all.py --parser pymupdf --batch-size 32
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shared.corpus_client import load_manifest
from shared.logging import configure_logging, get_logger
from shared.models import Source

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
        default="BAAI/bge-base-en-v1.5",
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
        return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    return {"completed": [], "failed": []}


def save_progress(progress: dict[str, list[str]]) -> None:
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2), encoding="utf-8")


def reindex_source_cli(source: Source, args: argparse.Namespace) -> bool:
    """Call reindex_source.py for a single source. Returns True on success."""
    import subprocess
    import sys

    cmd = [
        sys.executable,
        "scripts/reindex_source.py",
        "--source",
        source.source_id,
        "--parser",
        args.parser,
        "--batch-size",
        str(args.batch_size),
        "--embedding-model",
        args.embedding_model,
    ]
    if args.disable_image_extraction:
        cmd.append("--disable-image-extraction")

    logger.info(
        "starting_source_reindex",
        extra={"source_id": source.source_id, "command": " ".join(cmd)},
    )

    try:
        result = subprocess.run(cmd, check=False, capture_output=False, text=True)
        return result.returncode == 0
    except Exception as exc:  # pragma: no cover
        logger.error(
            "reindex_subprocess_failed",
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

    for source in sources:
        if source.source_id in progress["completed"]:
            logger.info(
                "skipping_completed_source",
                extra={"source_id": source.source_id},
            )
            continue

        success = reindex_source_cli(source, args)
        if success:
            progress["completed"].append(source.source_id)
            if source.source_id in progress["failed"]:
                progress["failed"].remove(source.source_id)
        else:
            if source.source_id not in progress["failed"]:
                progress["failed"].append(source.source_id)

        save_progress(progress)

    logger.info(
        "reindex_all_complete",
        extra={
            "completed": len(progress["completed"]),
            "failed": len(progress["failed"]),
        },
    )


if __name__ == "__main__":
    main()
