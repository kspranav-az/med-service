"""PDF text cleaning utilities.

Medical PDFs frequently split words across line breaks with hyphenation,
e.g. ``Classi-\nfication`` should become ``Classification``. They also
preserve physical line breaks in the middle of paragraphs, which produces
entities like ``Köln\nGermany`` and noisy sentence chunking.

This module normalises both issues while keeping true paragraph breaks
intact.
"""

from __future__ import annotations

import re


class TextCleaner:
    """Clean raw PDF-extracted text.

    Handles:
    - intra-page and cross-page hyphenation (``-\n``)
    - single newlines inside paragraphs converted to spaces
    - paragraph breaks (blank lines) preserved
    - repeated whitespace collapsed
    """

    def __init__(self) -> None:
        """Initialise with empty cross-page carry-over state."""
        self._carry: str = ""

    def reset(self) -> None:
        """Clear any pending cross-page hyphen fragment."""
        self._carry = ""

    def clean_page(self, text: str) -> str:
        """Return cleaned text for a single page.

        Any trailing hyphenated word fragment is carried over to the next
        page so that words split across page boundaries can be rejoined.

        Args:
            text: Raw text extracted from one PDF page.

        Returns:
            Cleaned page text.
        """
        text = f"{self._carry}{text}"
        self._carry = ""

        # Detect a trailing hyphen fragment that may continue on the next page.
        # Example: "... Classifi-" at end of page -> carry "Classifi".
        trailing_match = re.search(r"([a-zA-Z]{2,})-\s*$", text)
        if trailing_match:
            self._carry = trailing_match.group(1)
            text = text[: trailing_match.start()]

        return self._clean_text(text)

    def clean(self, text: str) -> str:
        """Clean arbitrary text without cross-page state.

        Args:
            text: Raw text to clean.

        Returns:
            Cleaned text.
        """
        return self._clean_text(text)

    def _clean_text(self, text: str) -> str:
        """Shared cleaning logic for both page and arbitrary text."""
        # Dehyphenate line-break continuations.
        # Matches "word-\nmore" or "word- \nmore" and joins them.
        text = re.sub(r"([a-zA-Z])-\s*\n\s*([a-zA-Z])", r"\1\2", text)

        # Preserve paragraph breaks with placeholders.
        text = re.sub(r"\n\s*\n+", "\x00PARA\x00", text)

        # Convert remaining single newlines (line wraps) to spaces.
        text = text.replace("\n", " ")
        text = text.replace("\r", " ")

        # Restore paragraph breaks.
        text = text.replace("\x00PARA\x00", "\n\n")

        # Collapse repeated whitespace.
        text = re.sub(r"[ \t]+", " ", text)

        return text.strip()
