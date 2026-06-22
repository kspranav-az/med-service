"""Pluggable entity extraction providers.

SciSpaCy is used as the default placeholder provider. It does not require
a UMLS license and produces entities with temporary internal type labels.
Phase 5 will introduce a UMLS-backed provider that conforms to the same
protocol.
"""

from __future__ import annotations

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


def _label_to_tui(label: str) -> str:
    """Map a SciSpaCy entity label to a temporary internal TUI."""
    return f"TUI-{label.upper()}"


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

        for ent in doc.ents:
            name = ent.text.strip()
            if not name or len(name) < 2:
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
