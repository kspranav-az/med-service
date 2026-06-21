"""Marker-pdf based PDF parser for layout-preserving extraction."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from shared.ingestion.base import Page, PDFParser
from shared.logging import get_logger

logger = get_logger(__name__)

# Optional heavy dependency; gracefully degrade if not installed.
try:
    from marker.config.parser import ConfigParser
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.output import text_from_rendered

    _MARKER_AVAILABLE = True
except ImportError:  # pragma: no cover
    ConfigParser = None  # type: ignore[misc, assignment]
    PdfConverter = None  # type: ignore[misc, assignment]
    create_model_dict = None  # type: ignore[misc, assignment]
    text_from_rendered = None  # type: ignore[misc, assignment]
    _MARKER_AVAILABLE = False


class MarkerPDFParser(PDFParser):
    """Layout-preserving PDF parser using Marker (v1.x API).

    This parser is significantly slower than PyMuPDF and is intended for
    books where table/equation/layout quality matters.
    """

    def __init__(self, source: Any, disable_image_extraction: bool = True) -> None:
        """Initialise the Marker parser.

        Args:
            source: Corpus source metadata.
            disable_image_extraction: Skip saving extracted images to disk.
        """
        super().__init__(source)
        self.disable_image_extraction = disable_image_extraction

        if not _MARKER_AVAILABLE:
            raise ImportError("marker-pdf is not installed. Run: uv sync --extra all --group dev")

    def parse(self, pdf_path: Path) -> list[Page]:
        """Extract pages from the PDF using Marker."""
        logger.info(
            "marker_parsing",
            extra={"source_id": self.source.source_id, "pdf_path": str(pdf_path)},
        )

        config = {
            "output_format": "markdown",
            "disable_image_extraction": self.disable_image_extraction,
            "paginate_output": True,
        }
        config_parser = ConfigParser(config)

        converter = PdfConverter(
            config=config_parser.generate_config_dict(),
            artifact_dict=create_model_dict(),
            processor_list=config_parser.get_processors(),
            renderer=config_parser.get_renderer(),
            llm_service=config_parser.get_llm_service(),
        )

        rendered = converter(str(pdf_path))
        full_text, _, _ = text_from_rendered(rendered)

        pages = self._split_by_pages(full_text)
        logger.info(
            "marker_parsed",
            extra={"source_id": self.source.source_id, "extracted_pages": len(pages)},
        )
        return pages

    def _split_by_pages(self, text: str) -> list[Page]:
        """Split paginated Marker output into per-page text blocks.

        Marker inserts separators like ``\n\n{1}\\n----------------\\n\n``
        when ``paginate_output`` is enabled. We split on those markers and
        assign page numbers.
        """
        # Match markers of the form:
        # \n\n{PAGE_NUMBER}\n----------------\n\n
        page_pattern = re.compile(r"\n\n\{(\d+)\}\n-+(?:\n\n|\n)")
        matches = list(page_pattern.finditer(text))

        if not matches:
            # No pagination markers found; return the whole text as page 1.
            return [
                Page(
                    source_id=self.source.source_id,
                    page_number=1,
                    text=text.strip(),
                )
            ]

        pages: list[Page] = []
        for i, match in enumerate(matches):
            page_number = int(match.group(1))
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            page_text = text[start:end].strip()
            if page_text:
                pages.append(
                    Page(
                        source_id=self.source.source_id,
                        page_number=page_number,
                        text=page_text,
                    )
                )

        return pages
