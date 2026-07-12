"""Tests for partset page cache paths."""

from PIL import Image

from pipeline.local_cache import LocalCache
from pipeline.page_dimensions import PORTRAIT


def _write_png(path, size: tuple[int, int]) -> None:
    Image.new("L", size, 255).save(path)


def test_partset_page_cache_round_trip(tmp_path) -> None:
    cache = LocalCache(tmp_path, download=lambda _key, _dest: None)
    partset_id = "pub01"
    pages_dir = tmp_path / "convert"
    lowres_src = pages_dir / "lowres"
    lowres_src.mkdir(parents=True)
    _write_png(lowres_src / "page-1.png", PORTRAIT.lowres_size)

    cache.copy_partset_pages_tree(partset_id, pages_dir)
    dest = cache.ensure_partset_page(partset_id, "lowres", 1)
    assert Image.open(dest).size == PORTRAIT.lowres_size

    cache.invalidate_partset_pages(partset_id)
    assert not cache.partset_has_kind(partset_id, "lowres")
