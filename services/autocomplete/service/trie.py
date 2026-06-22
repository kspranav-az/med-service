"""Character-level prefix trie for fast entity autocomplete."""

from __future__ import annotations

from typing import Any, TypeVar

T = TypeVar("T")


class _TrieNode:
    """Internal trie node."""

    def __init__(self) -> None:
        self.children: dict[str, _TrieNode] = {}
        self.values: list[Any] = []


class EntityTrie:
    """Case-insensitive prefix trie indexed by entity terms and aliases."""

    def __init__(self) -> None:
        """Initialise an empty trie."""
        self._root = _TrieNode()
        self._size = 0

    def insert(self, term: str, value: Any) -> None:
        """Insert a term and associated value into the trie.

        Args:
            term: Entity term or alias.
            value: Any object to return on match (typically an Entity dict).
        """
        node = self._root
        for ch in term.lower():
            node = node.children.setdefault(ch, _TrieNode())
        if not node.values:
            self._size += 1
        node.values.append(value)

    def prefix_search(self, prefix: str, limit: int = 10) -> list[Any]:
        """Return up to ``limit`` values whose keys start with ``prefix``.

        Args:
            prefix: Query prefix.
            limit: Maximum number of results.

        Returns:
            List of values stored under matching prefixes.
        """
        node: _TrieNode | None = self._root
        for ch in prefix.lower():
            if node is None:
                return []
            node = node.children.get(ch)
            if node is None:
                return []

        assert node is not None
        results: list[Any] = []
        self._collect(node, results, limit)
        return results

    def _collect(self, node: _TrieNode, results: list[Any], limit: int) -> None:
        """Depth-first collection of values up to ``limit``."""
        if len(results) >= limit:
            return

        for value in node.values:
            results.append(value)
            if len(results) >= limit:
                return

        for child in node.children.values():
            self._collect(child, results, limit)
            if len(results) >= limit:
                return

    def __len__(self) -> int:
        """Return the number of distinct terms in the trie."""
        return self._size
