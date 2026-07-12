"""Tests for part PDF assembly."""

from pipeline.paste_layout import page_dims_inches, vertical_layout
from pipeline.paste_segments import (
    _pdf_document_subject,
    _pdf_document_title,
    _reportlab_pagesize,
)
from reportlab.lib.pagesizes import A4, letter, landscape as landscape_page


def test_pdf_document_title_uses_part_and_score_title() -> None:
    assert _pdf_document_title("Violin I", "Beethoven", "Symphony No. 5") == (
        "Violin I — Symphony No. 5"
    )


def test_pdf_document_subject_uses_composer_and_title() -> None:
    assert _pdf_document_subject("Beethoven", "Symphony No. 5") == "Beethoven: Symphony No. 5"


def test_pdf_document_title_falls_back_to_composer() -> None:
    assert _pdf_document_title("Cello", "Bach", "") == "Cello — Bach"


def test_pdf_document_title_part_name_only() -> None:
    assert _pdf_document_title("Cello", "", "") == "Cello"


def test_page_dims_inches_landscape_swaps_letter() -> None:
    assert page_dims_inches("letter", "landscape") == (11, 8.5)


def test_page_dims_inches_portrait_letter() -> None:
    assert page_dims_inches("letter", "portrait") == (8.5, 11)


def test_reportlab_pagesize_landscape_letter() -> None:
    assert _reportlab_pagesize("letter", "landscape") == landscape_page(letter)


def test_reportlab_pagesize_portrait_a4() -> None:
    assert _reportlab_pagesize("a4", "portrait") == A4


def test_vertical_layout_landscape_is_positive() -> None:
    bottom, top = vertical_layout(8.5, "landscape")
    assert bottom == 0.4
    assert top == 8.0


def test_vertical_layout_portrait_letter() -> None:
    bottom, top = vertical_layout(11, "portrait")
    assert bottom == 0.25
    assert top == 10.75
