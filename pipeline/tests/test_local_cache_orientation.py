"""Tests for score page cache copy behavior."""

from PIL import Image

from pipeline.local_cache import LocalCache
from pipeline.page_dimensions import LANDSCAPE, PORTRAIT


def _write_png(path, size: tuple[int, int]) -> None:
    Image.new("L", size, 255).save(path)


def test_invalidate_score_pages_keeps_pdf(tmp_path) -> None:
    cache = LocalCache(tmp_path, download=lambda _key, _dest: None)
    score_id = "abc12"
    pdf_path = cache.score_pdf_path(score_id)
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"%PDF-1.4")

    for kind in ("lowres", "highres", "thumbs"):
        kind_dir = cache.score_kind_dir(score_id, kind)
        kind_dir.mkdir(parents=True)
        _write_png(kind_dir / "page-1.png", PORTRAIT.lowres_size)

    cache.invalidate_score_pages(score_id)

    assert pdf_path.is_file()
    assert not cache.score_has_kind(score_id, "lowres")
    assert not cache.score_has_kind(score_id, "highres")
    assert not cache.score_has_kind(score_id, "thumbs")


def test_copy_pages_tree_overwrites_existing_png(tmp_path) -> None:
    cache = LocalCache(tmp_path, download=lambda _key, _dest: None)
    score_id = "abc12"
    pages_dir = tmp_path / "convert"
    lowres_src = pages_dir / "lowres"
    highres_src = pages_dir / "highres"
    lowres_src.mkdir(parents=True)
    highres_src.mkdir()
    _write_png(lowres_src / "page-1.png", PORTRAIT.lowres_size)
    _write_png(highres_src / "page-1.png", PORTRAIT.lowres_size)

    cache.copy_pages_tree(score_id, pages_dir)
    dest = cache.score_page_path(score_id, "lowres", 1)
    assert Image.open(dest).size == PORTRAIT.lowres_size
    assert cache.canonical_page_paths(dest.parent) == [dest]

    _write_png(lowres_src / "page-1.png", LANDSCAPE.lowres_size)
    cache.copy_pages_tree(score_id, pages_dir)
    assert Image.open(dest).size == LANDSCAPE.lowres_size
