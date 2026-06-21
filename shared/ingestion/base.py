"""Base abstractions for PDF ingestion."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from shared.models import Source


@dataclass
class Page:
    """A single page extracted from a PDF."""

    source_id: str
    page_number: int
    text: str


class PDFParser(ABC):
    """Abstract base class for PDF text extraction."""

    def __init__(self, source: Source) -> None:
        """Initialise the parser for a specific source.

        Args:
            source: Corpus source metadata.
        """
        self.source = source

    @abstractmethod
    def parse(self, pdf_path: Path) -> list[Page]:
        """Extract pages from the given PDF.

        Args:
            pdf_path: Absolute path to the PDF file.

        Returns:
            List of extracted pages.
        """
        raise NotImplementedError
