"""Tests for shared.ingestion.text_cleaner."""

from __future__ import annotations

import pytest

from shared.ingestion.text_cleaner import TextCleaner


@pytest.fixture
def cleaner() -> TextCleaner:
    return TextCleaner()


def test_dehyphenates_line_break(cleaner: TextCleaner) -> None:
    raw = "The patient had Classi-\nfication criteria."
    assert cleaner.clean(raw) == "The patient had Classification criteria."


def test_dehyphenates_line_break_with_space(cleaner: TextCleaner) -> None:
    raw = "The patient had Classi- \nfication criteria."
    assert cleaner.clean(raw) == "The patient had Classification criteria."


def test_normalises_single_newlines(cleaner: TextCleaner) -> None:
    raw = "First line\nsecond line"
    assert cleaner.clean(raw) == "First line second line"


def test_preserves_paragraph_breaks(cleaner: TextCleaner) -> None:
    raw = "Paragraph one.\n\nParagraph two."
    assert cleaner.clean(raw) == "Paragraph one.\n\nParagraph two."


def test_collapse_repeated_whitespace(cleaner: TextCleaner) -> None:
    raw = "Too    many     spaces"
    assert cleaner.clean(raw) == "Too many spaces"


def test_cross_page_hyphenation(cleaner: TextCleaner) -> None:
    page1 = cleaner.clean_page("The Classifi-")
    page2 = cleaner.clean_page("cation was severe.")
    assert page1 == "The"
    assert page2 == "Classification was severe."


def test_cross_page_no_hyphen(cleaner: TextCleaner) -> None:
    page1 = cleaner.clean_page("The patient was stable.")
    page2 = cleaner.clean_page("No issues found.")
    assert page1 == "The patient was stable."
    assert page2 == "No issues found."
