"""Client for discovering and reading corpus documents."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from shared.config import settings
from shared.logging import get_logger
from shared.models import Source

logger = get_logger(__name__)


def _manifest_path() -> Path:
    """Return the resolved manifest file path."""
    return settings.corpus_root / "manifest.json"


def _normalise_book(raw: dict[str, object]) -> dict[str, object]:
    """Map manifest field names to the :class:`Source` schema.

    The manifest uses ``id``, ``file`` and ``pages``; the model uses
    ``source_id``, ``filename`` and ``total_pages``.
    """
    return {
        "source_id": raw.get("id"),
        "filename": raw.get("file"),
        "title": raw.get("title"),
        "domain": raw.get("domain"),
        "tags": raw.get("tags"),
        "path": raw.get("path"),
        "total_pages": raw.get("pages", 0),
    }


def load_manifest() -> list[Source]:
    """Load and validate the corpus manifest.

    Returns:
        List of :class:`Source` records from ``data/corpus/manifest.json``.

    Raises:
        FileNotFoundError: If the manifest is missing.
        ValueError: If the manifest JSON is malformed.
    """
    path = _manifest_path()
    if not path.exists():
        logger.error("manifest_not_found", extra={"manifest_path": str(path)})
        raise FileNotFoundError(f"Corpus manifest not found: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.error("manifest_parse_failed", extra={"error": str(exc)})
        raise ValueError(f"Failed to parse manifest: {exc}") from exc

    books = data.get("books", [])
    sources = [Source.model_validate(_normalise_book(book)) for book in books]
    logger.info("manifest_loaded", extra={"total_books": len(sources)})
    return sources


def get_source_by_id(source_id: str) -> Source | None:
    """Return the source with the given id, or None if not found."""
    for source in load_manifest():
        if source.source_id == source_id:
            return source
    return None


def resolve_source_path(source: Source) -> Path:
    """Resolve a source's relative path to an absolute file path."""
    return (settings.corpus_root / source.path).resolve()


def list_source_paths() -> Iterable[tuple[Source, Path]]:
    """Yield ``(Source, absolute_path)`` tuples for every manifest entry."""
    for source in load_manifest():
        yield source, resolve_source_path(source)


def source_exists(source: Source) -> bool:
    """Return True if the source's PDF exists on disk."""
    return resolve_source_path(source).is_file()
