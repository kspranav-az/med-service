"""Reciprocal Rank Fusion (RRF) for merging ranked result lists.

RRF combines results from multiple retrieval strategies without requiring
comparable score scales. Each list contributes ``1 / (k + rank)`` per item,
where ``rank`` is the zero-based position in that list.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable
from typing import Any


def reciprocal_rank_fusion[T, K: Hashable](
    result_lists: list[list[T]],
    key_func: Callable[[T], K] | None = None,
    top_k: int | None = None,
    k: int = 60,
) -> list[tuple[T, float]]:
    """Merge multiple ranked lists using reciprocal rank fusion.

    Args:
        result_lists: Ranked result lists. Earlier items in each list are
            considered higher ranked.
        key_func: Function to extract a hashable key from each item. If
            omitted, the item itself must be hashable.
        top_k: Number of fused results to return. Defaults to all.
        k: RRF ranking constant.

    Returns:
        Fused results as ``(item, score)`` tuples sorted by descending score.
    """
    scores: dict[Any, float] = {}
    items: dict[Any, T] = {}

    for result_list in result_lists:
        for rank, item in enumerate(result_list):
            key: Any = key_func(item) if key_func is not None else item
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            items[key] = item

    sorted_keys = sorted(scores, key=lambda k: scores[k], reverse=True)
    output = [(items[key], round(scores[key], 4)) for key in sorted_keys]

    if top_k is not None:
        return output[:top_k]
    return output
