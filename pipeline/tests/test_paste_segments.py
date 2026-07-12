"""Tests for part PDF assembly."""

from pathlib import Path

from PIL import Image

from pipeline.paste_layout import page_dims_inches, vertical_layout
from pipeline.paste_segments import (
    _add_images,
    _pdf_document_subject,
    _pdf_document_title,
    _reportlab_pagesize,
    create_part,
)
from reportlab.lib.pagesizes import A4, letter, landscape as landscape_page
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas


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


def test_add_images_scales_oversized_segment_to_fit(tmp_path: Path) -> None:
    seg = tmp_path / "tall.png"
    Image.new("L", (100, 4000), 0).save(seg)
    pdf = tmp_path / "out.pdf"
    doc = canvas.Canvas(str(pdf), pagesize=letter)
    _add_images(
        doc,
        [{"file": seg, "label": "", "cue": False}],
        x=0.75,
        y=10.05,
        vspace=0.1,
        min_y_in=0.5 * inch,
    )
    doc.save()
    assert pdf.stat().st_size > 0


def test_create_part_oversized_segment_does_not_raise(tmp_path: Path) -> None:
    seg = tmp_path / "tall.png"
    Image.new("L", (200, 3500), 0).save(seg)
    out = tmp_path / "part.pdf"
    create_part(
        title="T",
        composer="C",
        part_name="1",
        partset_id="abc12",
        sep=0.1,
        pages=[[{"file": seg, "label": "", "cue": False}]],
        outfile=out,
        pagesize="letter",
        orientation="portrait",
    )
    assert out.is_file() and out.stat().st_size > 0
