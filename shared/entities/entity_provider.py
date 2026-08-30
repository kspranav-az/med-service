"""Pluggable entity extraction providers.

SciSpaCy is used as the default placeholder provider. It does not require
a UMLS license and produces entities with temporary internal type labels.
Phase 5 will introduce a UMLS-backed provider that conforms to the same
protocol.
"""

from __future__ import annotations

import re
import string
import unicodedata
from collections.abc import Iterable
from typing import Any, Protocol, runtime_checkable

from shared.logging import get_logger
from shared.models import Entity

logger = get_logger(__name__)

# Optional SciSpaCy dependency; gracefully degrade if unavailable.
try:
    import spacy

    _SPACY_AVAILABLE = True
except ImportError:  # pragma: no cover
    spacy = None  # type: ignore[assignment]
    _SPACY_AVAILABLE = False

DEFAULT_SCISPACY_MODEL = "en_core_sci_md"

# Characters that should not appear at the start or end of a medical term.
_TRAIL_PUNCT = set(string.punctuation + "–—−―‒‐…“”‘’")

# Patterns used to filter obviously noisy entities extracted from PDFs.
_AUTHOR_PART_PATTERN = re.compile(
    # Surname: capitalised word, optionally preceded by de/van/von. Apostrophes
    # are allowed; hyphens are not, so medical fragments like "X-ray" are not
    # mistaken for surnames.
    r"^(?:(?:[Dd]e|[Vv]an|[Vv]on)\s+)?[A-Z][a-zA-Z']+"
    # Optional initials, e.g. "AB", "A-B".
    r"(?:\s+[A-Z](?:[A-Z]?|-[A-Z]))?"
    # Optional "Jr" suffix.
    r"(?:\s+Jr\.?)?$"
)
_AUTHOR_COMMA_PATTERN = re.compile(r",\s*[A-Z]")
_URL_EMAIL_PATTERN = re.compile(r"https?://|www\.|@[\w.-]+\.")
_REFERENCE_PATTERN = re.compile(r"\b(\d{4};\d+(:\d+)?-\d+|et\s+al|doi:|pmid:|ISBN|ISSN)\b")
_HEADER_FOOTER_WORDS = {
    "introduction",
    "conclusion",
    "references",
    "index",
    "contents",
    "table of contents",
    "abstract",
    "summary",
    "acknowledgements",
    "copyright",
    "springer",
    "elsevier",
    "wiley",
    "lippincott",
    "saunders",
    "chapter",
    "page",
    "figure",
    "fig",
    "table",
    "volume",
    "part",
}
_HEADER_FOOTER_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(word) for word in _HEADER_FOOTER_WORDS) + r")\b"
)


def _looks_like_author(name: str) -> bool:
    """Return True if ``name`` looks like an author or author list."""
    # Comma followed by an initial is a strong author signal, e.g. "Smith, AB"
    # or "Wallner SJ, Reusche E".
    if _AUTHOR_COMMA_PATTERN.search(name):
        return True

    parts = re.split(r"\s*,\s*|\s+\band\b\s+", name)
    if len(parts) > 1 and all(
        _AUTHOR_PART_PATTERN.match(part.strip()) for part in parts if part.strip()
    ):
        return True

    return bool(_AUTHOR_PART_PATTERN.match(name))


def _label_to_tui(label: str) -> str:
    """Map a SciSpaCy entity label to a temporary internal TUI."""
    return f"TUI-{label.upper()}"


def _is_noise_entity(name: str) -> bool:
    """Return True if ``name`` is clearly not a useful medical term.

    Filters out author names, URLs, citations, headers/footers, and
    fragments that are too short, too long, numeric, or mostly punctuation.
    """
    if not name:
        return True

    # Too short or too long.
    if len(name) < 3 or len(name) > 150:
        return True

    # Numeric-only strings are not useful medical terms.
    if re.fullmatch(r"\d+", name.strip()):
        return True

    # Mostly non-word characters.
    alphanumeric = sum(1 for c in name if c.isalnum() or c.isspace())
    if alphanumeric == 0 or alphanumeric / len(name) < 0.5:
        return True

    # Left-over PDF artifacts (control chars, format chars, private-use glyphs,
    # replacement characters) mean the entity is corrupted.
    if any(
        unicodedata.category(c) in ("Cc", "Cf", "Co") or ord(c) == 0xFFFD
        for c in name
    ):
        return True

    # URLs / emails.
    if _URL_EMAIL_PATTERN.search(name):
        return True

    # Reference / citation fragments.
    if _REFERENCE_PATTERN.search(name):
        return True

    # Leading or trailing punctuation/dashes are usually fragments, e.g.
    # "cord–", "’s site", "sphincter ani”", "P.O.".
    if name[0] in _TRAIL_PUNCT or name[-1] in _TRAIL_PUNCT:
        return True

    # Author names like "Smith AB", "Smith, AB", "de Vries PA",
    # "Templeton JH Jr", or "Wallner SJ, Reusche E".
    if _looks_like_author(name):
        return True

    # Header/footer/book metadata words.
    if _HEADER_FOOTER_RE.search(name.lower()):
        return True

    return False


@runtime_checkable
class EntityProvider(Protocol):
    """Protocol for entity extraction providers."""

    def extract(self, text: str, source_id: str | None = None) -> list[Entity]:
        """Extract entities from ``text``.

        Args:
            text: Input text.
            source_id: Optional origin document identifier.

        Returns:
            List of extracted :class:`Entity` objects.
        """
        ...


class SciSpaCyEntityProvider:
    """Entity provider backed by a SciSpaCy spaCy model."""

    def __init__(self, model_name: str = DEFAULT_SCISPACY_MODEL) -> None:
        """Load the SciSpaCy model.

        Args:
            model_name: SciSpaCy model package name.
        """
        if not _SPACY_AVAILABLE or spacy is None:
            raise RuntimeError(
                "spacy/scispacy is not installed. "
                "Install with: uv pip install scispacy spacy "
                "and the model package (e.g. en_core_sci_md)."
            )

        self.model_name = model_name
        logger.info("loading_scispacy_model", extra={"model": model_name})
        self._nlp = spacy.load(model_name)

    def extract(self, text: str, source_id: str | None = None) -> list[Entity]:
        """Extract entities from ``text`` using SciSpaCy NER."""
        doc = self._nlp(text)
        entities: list[Entity] = []
        seen: set[str] = set()
        dropped = 0

        for ent in doc.ents:
            name = ent.text.strip()
            if not name or len(name) < 2:
                dropped += 1
                continue

            if _is_noise_entity(name):
                dropped += 1
                continue

            key = f"{name.lower()}:{ent.label_}"
            if key in seen:
                continue
            seen.add(key)

            entities.append(
                Entity(
                    name=name,
                    cui=None,
                    tuis=[_label_to_tui(ent.label_)],
                    aliases=[],
                    source=source_id,
                    entity_type=ent.label_,
                )
            )

        if dropped:
            logger.debug(
                "filtered_noise_entities",
                extra={"source": source_id, "dropped": dropped},
            )
        return entities

    def extract_from_pages(
        self,
        pages: Iterable[tuple[str, Any]],
    ) -> list[Entity]:
        """Extract entities from a sequence of (source_id, text) pages.

        Args:
            pages: Iterable of ``(source_id, text)`` tuples. ``text`` may be
                a string or an object with a ``text`` attribute (e.g. Page).

        Returns:
            Deduplicated list of entities across all pages.
        """
        all_entities: list[Entity] = []
        global_seen: set[str] = set()

        for source_id, text_or_page in pages:
            text = getattr(text_or_page, "text", text_or_page)
            if not isinstance(text, str) or not text.strip():
                continue

            for entity in self.extract(text, source_id=source_id):
                key = f"{entity.name.lower()}:{','.join(entity.tuis)}"
                if key in global_seen:
                    continue
                global_seen.add(key)
                all_entities.append(entity)

        logger.info(
            "extracted_entities",
            extra={"model": self.model_name, "entities": len(all_entities)},
        )
        return all_entities


def get_entity_provider(model_name: str | None = None) -> EntityProvider:
    """Factory for the default entity provider.

    Args:
        model_name: SciSpaCy model name. Defaults to ``en_core_sci_md``.

    Returns:
        Configured entity provider.
    """
    return SciSpaCyEntityProvider(model_name=model_name or DEFAULT_SCISPACY_MODEL)
