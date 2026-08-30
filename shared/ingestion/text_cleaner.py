"""PDF text cleaning utilities.

Medical PDFs frequently split words across line breaks with hyphenation,
e.g. ``Classi-\nfication`` should become ``Classification``. They also
preserve physical line breaks in the middle of paragraphs, which produces
entities like ``Köln\nGermany`` and noisy sentence chunking. Finally,
PDF extractors emit control characters, private-use glyphs, and Unicode
replacement characters that must be removed before indexing.

This module normalises all three issues while keeping true paragraph breaks
intact.
"""

from __future__ import annotations

import re
import unicodedata


class TextCleaner:
    """Clean raw PDF-extracted text.

    Handles:
    - intra-page and cross-page hyphenation (``-\n``)
    - single newlines inside paragraphs converted to spaces
    - paragraph breaks (blank lines) preserved
    - repeated whitespace collapsed
    - control characters, private-use glyphs, and replacement chars removed
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

        # Sanitize PDF artifacts: control chars, private-use glyphs,
        # replacement characters, zero-width spaces, soft hyphens, BOM.
        text = self._sanitize(text)

        # Collapse repeated whitespace.
        text = re.sub(r"[ \t]+", " ", text)

        return text.strip()

    @staticmethod
    def _sanitize(text: str) -> str:
        """Remove non-printable PDF artifacts while keeping valid text.

        Removes ASCII control characters (except tab/newline/space),
        Unicode replacement characters, private-use glyphs, and formatting
        characters such as zero-width spaces, soft hyphens, and BOM.
        """
        cleaned_chars: list[str] = []
        for char in text:
            category = unicodedata.category(char)
            code = ord(char)

            # Keep normal whitespace and visible characters.
            if char in "\t\n\r ":
                cleaned_chars.append(char)
                continue

            # Drop control characters (Cc), format characters (Cf) such as
            # soft hyphen / zero-width spaces, and private-use glyphs (Co).
            if category in ("Cc", "Cf", "Co"):
                continue

            # Drop Unicode replacement character explicitly.
            if code == 0xFFFD:
                continue

            cleaned_chars.append(char)

        return "".join(cleaned_chars)
