"""Extract medical entities from the corpus using SciSpaCy."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from shared.config import settings
from shared.corpus_client import list_source_paths
from shared.entities import SciSpaCyEntityProvider
from shared.ingestion import ParserType, get_parser
from shared.logging import configure_logging, get_logger
from shared.models import Entity

logger = get_logger(__name__)

DEFAULT_OUTPUT_DIR = settings.project_root / "data" / "processed" / "entities"
DEFAULT_OUTPUT_FILE = DEFAULT_OUTPUT_DIR / "scispacy_entities.json"


def _iter_pages() -> Iterable[tuple[str, Any]]:
    """Yield (source_id, page) tuples for every corpus page."""
    for source, path in list_source_paths():
        if not path.is_file():
            logger.warning(
                "source_file_missing",
                extra={"source_id": source.source_id, "path": str(path)},
            )
            continue

        logger.info("extracting_entities", extra={"source_id": source.source_id})
        parser = get_parser(source, ParserType.PYMUPDF)
        for page in parser.parse(path):
            yield source.source_id, page


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract medical entities from the corpus.")
    parser.add_argument(
        "--output-file",
        type=Path,
        default=None,
        help="Destination JSON path. Defaults to data/processed/entities/scispacy_entities.json.",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default=None,
        help="SciSpaCy model name. Defaults to en_core_sci_md.",
    )
    return parser.parse_args()


def main(
    output_file: Path | str | None = None,
    model_name: str | None = None,
) -> Path:
    """Extract entities and write them to JSON.

    Args:
        output_file: Destination JSON path. Defaults to
            ``data/processed/entities/scispacy_entities.json``.
        model_name: SciSpaCy model name. Defaults to ``en_core_sci_md``.

    Returns:
        Path to the written JSON file.
    """
    configure_logging()

    if output_file is None and model_name is None:
        args = _parse_args()
        output_file = args.output_file
        model_name = args.model_name

    output_file = Path(output_file or DEFAULT_OUTPUT_FILE)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    provider = SciSpaCyEntityProvider(model_name=model_name or "en_core_sci_md")
    entities = provider.extract_from_pages(_iter_pages())

    records = [Entity.model_validate(entity).model_dump(mode="json") for entity in entities]
    output_file.write_text(json.dumps(records, indent=2), encoding="utf-8")

    logger.info(
        "entities_saved",
        extra={
            "count": len(records),
            "path": str(output_file),
            "model": provider.model_name,
        },
    )
    return output_file


if __name__ == "__main__":
    main()
