"""PyMuPDF-based PDF parser."""

from __future__ import annotations

from pathlib import Path

import fitz

from shared.ingestion.base import Page, PDFParser
from shared.logging import get_logger

logger = get_logger(__name__)


class PyMuPDFParser(PDFParser):
    """Fast, reliable PDF parser using PyMuPDF (fitz)."""

    def parse(self, pdf_path: Path) -> list[Page]:
        """Extract text from the PDF, one page at a time."""
        pages: list[Page] = []
        doc = fitz.open(pdf_path)
        logger.info(
            "pymupdf_parsing",
            extra={"source_id": self.source.source_id, "total_pages": len(doc)},
        )

        for page_idx in range(len(doc)):
            page = doc.load_page(page_idx)
            text = page.get_text("text").strip()
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
