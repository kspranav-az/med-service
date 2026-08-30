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
        ("Smith", True),
        ("Smith AB", True),
        ("Jones A-B", True),
        ("Smith, AB", True),
        ("de Vries PA", True),
        ("Templeton JH Jr", True),
        ("Wallner SJ, Reusche E", True),
        ("Smith DAJ", True),
        ("Smith,77", True),
        ("Smith LH Jr. L-glyceric aciduria", True),
        ("Smith's Anesthesia", True),
        ("Smith's Operative Surgery", True),
        ("Smith & Nephew", True),
        ("www.example.com", True),
        ("foo@bar.com", True),
        ("1984;19:1181-5", True),
        ("et al", True),
        ("References", True),
        ("Springer", True),
        ("Chapter 1", True),
        ("cord–", True),
        ("’s site", True),
        ("sphincter ani”", True),
        ("side laterally (Fig.", True),
        ("bladder.6", True),
        ("repair.4", True),
        ("cancer’s", True),
        ("kidney’s", True),
        ("bladder A", True),
        ("Cancer •", True),
        ("Cord blood cells", False),
        ("Laparoscopic appendectomy", False),
        ("General anaesthesia", False),
        ("11β-hydroxylase deficiency", False),
        ("Hirschsprung disease", False),
        ("S1–S4", False),
        ("X-ray", False),
        ("Smith-Lemli-Opitz syndrome", False),
        ("Down's syndrome", False),
    ],
)
def test_is_noise_entity(name: str, expected_noise: bool) -> None:
    assert _is_noise_entity(name) is expected_noise
