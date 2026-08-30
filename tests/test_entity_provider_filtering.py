"""Tests for SciSpaCyEntityProvider noise filtering."""

from __future__ import annotations

import pytest

from shared.entities.entity_provider import _is_noise_entity


@pytest.mark.parametrize(
    ("name", "expected_noise"),
    [
        ("", True),
        ("A", True),
        ("AB", True),
        ("1A", True),
        ("-3", True),
        ("123", True),
        ("Cord\x08\ufffd\ufffd", True),
        ("Smith AB", True),
        ("Jones A-B", True),
        ("www.example.com", True),
        ("foo@bar.com", True),
        ("1984;19:1181-5", True),
        ("et al", True),
        ("References", True),
        ("Springer", True),
        ("Chapter 1", True),
        ("Cord blood cells", False),
        ("Laparoscopic appendectomy", False),
        ("General anaesthesia", False),
        ("11β-hydroxylase deficiency", False),
        ("Hirschsprung disease", False),
    ],
)
def test_is_noise_entity(name: str, expected_noise: bool) -> None:
    assert _is_noise_entity(name) is expected_noise
