"""Fast fuzzy string matching using rapidfuzz."""

from __future__ import annotations

from typing import TypeVar

try:
    from rapidfuzz import fuzz, process

    _RAPIDFUZZ_AVAILABLE = True
except ImportError:  # pragma: no cover
    fuzz = None  # type: ignore[assignment]
    process = None  # type: ignore[assignment]
    _RAPIDFUZZ_AVAILABLE = False

T = TypeVar("T")


class FuzzyMatcher:
    """Levenshtein-style fuzzy matcher over a fixed candidate list."""

    def __init__(self, candidates: list[tuple[str, T]]) -> None:
        """Initialise the matcher.

        Args:
            candidates: List of ``(label, value)`` tuples.
        """
        if not _RAPIDFUZZ_AVAILABLE or process is None or fuzz is None:
            raise RuntimeError(
                "rapidfuzz is not installed. Install with: uv pip install rapidfuzz"
            )

        self._labels = [label for label, _ in candidates]
        self._values = [value for _, value in candidates]

    def search(
        self,
        query: str,
        limit: int = 10,
        score_cutoff: int = 80,
    ) -> list[tuple[T, float]]:
        """Return fuzzy matches for ``query``.

        Args:
            query: Input string (may contain typos).
            limit: Maximum number of matches.
            score_cutoff: Minimum similarity score (0–100).

        Returns:
            List of ``(value, score)`` tuples sorted by descending score.
        """
        results = process.extract(
            query,
            self._labels,
            scorer=fuzz.ratio,
            limit=limit,
            score_cutoff=score_cutoff,
        )
        return [(self._values[idx], float(score)) for _label, score, idx in results]  # type: ignore[misc]
