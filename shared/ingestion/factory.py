"""Factory for selecting PDF parser implementations."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from shared.ingestion.base import PDFParser
from shared.logging import get_logger
from shared.models import Source

logger = get_logger(__name__)


class ParserType(StrEnum):
    """Supported PDF parser backends."""

    PYMUPDF = "pymupdf"
    MARKER = "marker"


def get_parser(
    source: Source,
    parser_type: ParserType | str = ParserType.PYMUPDF,
    **kwargs: Any,
) -> PDFParser:
    """Return a configured PDF parser for the given source.

    Args:
        source: Corpus source metadata.
        parser_type: Parser backend to use.
        **kwargs: Additional parser-specific options.

    Returns:
        Configured parser instance.
    """
    parser_type = ParserType(str(parser_type).lower())

    if parser_type == ParserType.PYMUPDF:
        from shared.ingestion.pymupdf_parser import PyMuPDFParser

        return PyMuPDFParser(source)

    if parser_type == ParserType.MARKER:
        from shared.ingestion.marker_parser import MarkerPDFParser

        return MarkerPDFParser(source, **kwargs)

    raise ValueError(f"Unknown parser type: {parser_type}")
