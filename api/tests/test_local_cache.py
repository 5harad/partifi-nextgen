from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from pipeline.local_cache import LocalCache


def _cache(tmp_path: Path) -> LocalCache:
    def download(key: str, dest: Path) -> None:
        dest.write_bytes(f"payload:{key}".encode())

    return LocalCache(tmp_path, download=download)


def test_install_file_wins_if_dest_already_exists(tmp_path: Path) -> None:
    cache = _cache(tmp_path)
    dest = tmp_path / "scores" / "abc" / "lowres" / "page-1.png"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"existing")

    tmp = cache._temp_path(dest)
    tmp.write_bytes(b"new-bytes")
    cache._install_file(tmp, dest)

    assert dest.read_bytes() == b"existing"
    assert not tmp.exists()


def test_ensure_score_page_skips_download_when_cached(tmp_path: Path) -> None:
    cache = _cache(tmp_path)
    dest = cache.score_page_path("abc", "lowres", 1)
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"cached")

    calls: list[str] = []

    def download(key: str, path: Path) -> None:
        calls.append(key)
        path.write_bytes(b"x")

    cache.download = download
    result = cache.ensure_score_page("abc", "lowres", 1)

    assert result == dest
    assert calls == []


def test_ensure_score_page_raises_when_missing(tmp_path: Path) -> None:
    import pytest

    cache = _cache(tmp_path)
    with pytest.raises(FileNotFoundError, match="not in local cache"):
        cache.ensure_score_page("abc", "highres", 1)


def test_store_part_file_replaces_existing(tmp_path: Path) -> None:
    cache = _cache(tmp_path)
    dest = cache.part_path("pub1", "violin.pdf")
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"old-part")

    src = tmp_path / "violin.pdf"
    src.write_bytes(b"new-part")
    cache.store_part_file("pub1", src)

    assert dest.read_bytes() == b"new-part"


def test_write_preview_publishes_complete_dir(tmp_path: Path) -> None:
    cache = _cache(tmp_path)
    segments = tmp_path / "segments"
    segments.mkdir()
    (segments / "s0.png").write_bytes(b"seg0")
    (segments / "s1.png").write_bytes(b"seg1")

    cache.write_preview("ps1", "fingerprint", segments)
    preview = cache.preview_dir("ps1")

    assert preview.is_dir()
    assert (preview / "s0.png").read_bytes() == b"seg0"
    assert (preview / "s1.png").read_bytes() == b"seg1"


def test_ensure_score_pdf_downloads_when_missing(tmp_path: Path) -> None:
    cache = _cache(tmp_path)
    dest = cache.score_pdf_path("abc")
    calls: list[str] = []

    def download(key: str, path: Path) -> None:
        calls.append(key)
        path.write_bytes(b"%PDF-fake")

    cache.download = download
    result = cache.ensure_score_pdf("abc")

    assert result == dest
    assert dest.read_bytes() == b"%PDF-fake"
    assert calls == ["scores/abc_score.pdf"]


def test_page_image_url_includes_png_suffix() -> None:
    from app.services.segments import page_image_url

    assert page_image_url("priv1", 3, "lowres") == "/api/v1/partsets/priv1/page-image/3.png?res=lowres"


def test_preview_segment_url_includes_png_suffix() -> None:
    from app.services.preview import preview_segment_url

    assert preview_segment_url("priv1", 3) == "/api/v1/partsets/priv1/preview-segment/3.png"


def test_preview_segment_response_is_not_persistently_cached(tmp_path: Path) -> None:
    from app.routers.v1 import preview_segment_image

    path = tmp_path / "s0.png"
    path.write_bytes(b"preview")
    cache = Mock()
    cache.preview_segment_path.return_value = path

    with (
        patch(
            "app.routers.v1.get_partset_by_private_id",
            return_value=SimpleNamespace(id="partset1"),
        ),
        patch("app.routers.v1.get_local_cache", return_value=cache),
    ):
        response = preview_segment_image("priv1", 0, db=Mock())

    assert response.headers["cache-control"] == "private, no-store"


def test_page_image_response_is_not_persistently_cached(tmp_path: Path) -> None:
    from app.routers.v1 import _page_image_response

    path = tmp_path / "page-1.png"
    path.write_bytes(b"page")
    partset = SimpleNamespace(score_id="score1")
    db = Mock()
    db.get.return_value = SimpleNamespace()

    with (
        patch("app.routers.v1.get_partset_by_private_id", return_value=partset),
        patch("app.routers.v1.ensure_page_image_path", return_value=path),
    ):
        response = _page_image_response("priv1", 1, "lowres", db)

    assert response.headers["cache-control"] == "private, no-store"


def test_write_preview_replaces_existing_files(tmp_path: Path) -> None:
    cache = _cache(tmp_path)
    preview = cache.preview_dir("ps1")
    preview.mkdir(parents=True)
    (preview / "s0.png").write_bytes(b"old")
    (preview / ".fingerprint").write_text("old-fp")

    segments = tmp_path / "segments"
    segments.mkdir()
    (segments / "s0.png").write_bytes(b"new")

    cache.write_preview("ps1", "fingerprint", segments)

    assert (preview / "s0.png").read_bytes() == b"new"
