from pathlib import Path

import fitz
import pytest

from split_two_up import split_two_up_pdf


@pytest.mark.parametrize(
    ("source_rotation", "user_rotation"),
    [(0, 0), (90, 270), (180, 180), (270, 90)],
)
def test_split_two_up_emits_portrait_left_then_right_pages(
    tmp_path: Path,
    source_rotation: int,
    user_rotation: int,
) -> None:
    source_path = tmp_path / "source.pdf"
    source = fitz.open()
    page = source.new_page(width=792, height=612)
    page.insert_text((80, 300), "LEFT", fontsize=60)
    page.insert_text((480, 300), "RIGHT", fontsize=60)
    page.set_rotation(source_rotation)
    source.save(source_path)
    source.close()

    output_path = tmp_path / "split.pdf"
    assert split_two_up_pdf(source_path, output_path, rotation_degrees=user_rotation) == 2

    result = fitz.open(output_path)
    assert len(result) == 2
    assert all(page.rect.width < page.rect.height for page in result)
    text = [page.get_text() for page in result]
    assert "LEFT" in text[0]
    assert "RIGH" in text[1]


def test_split_two_up_doubles_source_page_count(tmp_path: Path) -> None:
    source_path = tmp_path / "source.pdf"
    source = fitz.open()
    for _ in range(12):
        source.new_page(width=792, height=612)
    source.save(source_path)
    source.close()

    output_path = tmp_path / "split.pdf"
    assert split_two_up_pdf(source_path, output_path, rotation_degrees=0) == 24
    result = fitz.open(output_path)
    assert len(result) == 24
    assert all(page.rect.width < page.rect.height for page in result)
