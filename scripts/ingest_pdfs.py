"""Parse PDFs and save extracted text pages to disk.

Examples:
    uv run python scripts/ingest_pdfs.py --source urodynamics_iaps --parser pymupdf
    uv run python scripts/ingest_pdfs.py --parser marker --disable-image-extraction
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shared.corpus_client import get_source_by_id, load_manifest, resolve_source_path
from shared.ingestion import ParserType, get_parser
from shared.logging import configure_logging, get_logger

logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse corpus PDFs to text pages.")
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Source id to parse. If omitted, parse all sources.",
    )
    parser.add_argument(
        "--parser",
        type=str,
        default=ParserType.PYMUPDF,
        choices=[p.value for p in ParserType],
        help="PDF parser backend.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/outputs/parsed"),
        help="Directory to write parsed pages.",
    )
    parser.add_argument(
        "--disable-image-extraction",
        action="store_true",
        help="Disable image extraction for Marker parser.",
    )
    return parser.parse_args()


def save_pages(output_dir: Path, source_id: str, pages: list[dict[str, object]]) -> Path:
    out_file = output_dir / f"{source_id}.jsonl"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as f:
        for page in pages:
            f.write(json.dumps(page, ensure_ascii=False) + "\n")
    return out_file


def main() -> None:
    configure_logging()
    args = parse_args()

    output_dir = args.output_dir / args.parser
    output_dir.mkdir(parents=True, exist_ok=True)

    sources = [get_source_by_id(args.source)] if args.source else load_manifest()

    for source in sources:
        if source is None:
            logger.error("source_not_found", extra={"source_id": args.source})
            continue

        pdf_path = resolve_source_path(source)
        if not pdf_path.exists():
            logger.error(
                "pdf_not_found", extra={"source_id": source.source_id, "path": str(pdf_path)}
            )
            continue

        parser_kwargs = {}
        if args.parser == ParserType.MARKER:
            parser_kwargs["disable_image_extraction"] = args.disable_image_extraction

        parser = get_parser(source, parser_type=args.parser, **parser_kwargs)
        pages = parser.parse(pdf_path)

        page_dicts = [
            {
                "source_id": page.source_id,
                "page_number": page.page_number,
                "text": page.text,
            }
            for page in pages
        ]

        out_file = save_pages(output_dir, source.source_id, page_dicts)
        logger.info(
            "saved_parsed_pages",
            extra={
                "source_id": source.source_id,
                "pages": len(page_dicts),
                "output_file": str(out_file),
            },
        )


if __name__ == "__main__":
    main()
