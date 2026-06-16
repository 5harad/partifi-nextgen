import pytest
from pathlib import Path

from pipeline.pdf_fonts import (
    TIMES_ROMAN,
    PARTIFI_NOTO_CJK,
    PARTIFI_NOTO_SANS,
    _find_font,
    has_cjk,
    header_font_name,
    is_latin_only,
    NOTO_CJK_CANDIDATES,
    NOTO_SANS_CANDIDATES,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Beethoven", True),
        ("Dvořák", True),
        ("Café", True),
        ("No. 2 in B♭", True),
        ("", True),
        ("梁祝", False),
        ("Violin 小提琴", False),
        ("Пётр", False),
    ],
)
def test_is_latin_only(text: str, expected: bool) -> None:
    assert is_latin_only(text) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("梁祝", True),
        ("Violin", False),
        ("Violin 小提琴", True),
        ("ひらがな", True),
        ("한글", True),
    ],
)
def test_has_cjk(text: str, expected: bool) -> None:
    assert has_cjk(text) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Beethoven", TIMES_ROMAN),
        ("Dvořák", TIMES_ROMAN),
        ("梁祝", PARTIFI_NOTO_CJK),
        ("Пётр", PARTIFI_NOTO_SANS),
    ],
)
def test_header_font_name(text: str, expected: str) -> None:
    if expected != TIMES_ROMAN and _find_font(NOTO_SANS_CANDIDATES) is None:
        pytest.skip("Noto Sans not installed")
    if expected == PARTIFI_NOTO_CJK and _find_font(NOTO_CJK_CANDIDATES) is None:
        pytest.skip("Noto CJK not installed")
    assert header_font_name(text) == expected


def test_create_part_with_cjk_title(tmp_path: Path) -> None:
    if _find_font(NOTO_SANS_CANDIDATES) is None or _find_font(NOTO_CJK_CANDIDATES) is None:
        pytest.skip("Noto fonts not installed")

    from PIL import Image

    from pipeline.paste_segments import create_part

    seg_path = tmp_path / "seg.png"
    Image.new("RGB", (100, 100), "white").save(seg_path)

    outfile = tmp_path / "part.pdf"
    create_part(
        title="梁祝",
        composer="何占豪",
        part_name="小提琴",
        partset_id="abc123",
        sep=0.1,
        pages=[[{"file": seg_path, "label": "", "cue": False}]],
        outfile=outfile,
    )

    assert outfile.is_file()
    assert outfile.read_bytes()[:4] == b"%PDF"
