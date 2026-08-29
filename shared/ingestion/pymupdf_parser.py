"""PyMuPDF-based PDF parser."""

from __future__ import annotations

from pathlib import Path

import fitz

from shared.ingestion.base import Page, PDFParser
from shared.ingestion.text_cleaner import TextCleaner
from shared.logging import get_logger
from shared.models import Source

logger = get_logger(__name__)


class PyMuPDFParser(PDFParser):
    """Fast, reliable PDF parser using PyMuPDF (fitz)."""

    def __init__(self, source: Source) -> None:
        super().__init__(source)
        self._cleaner = TextCleaner()

    def parse(self, pdf_path: Path) -> list[Page]:
        """Extract text from the PDF, one page at a time."""
        pages: list[Page] = []
        doc = fitz.open(pdf_path)
        self._cleaner.reset()
        logger.info(
            "pymupdf_parsing",
            extra={"source_id": self.source.source_id, "total_pages": len(doc)},
        )

        for page_idx in range(len(doc)):
            page = doc.load_page(page_idx)
            raw_text = page.get_text("text").strip()
            text = self._cleaner.clean_page(raw_text)
            if text:
                pages.append(
                    Page(
                        source_id=self.source.source_id,
                        page_number=page_idx + 1,
                        text=text,
                    )
                )

        doc.close()
        logger.info(
            "pymupdf_parsed",
            extra={"source_id": self.source.source_id, "extracted_pages": len(pages)},
        )
        return pages
