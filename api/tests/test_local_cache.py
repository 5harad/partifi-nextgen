from pathlib import Path

from pipeline.local_cache import LocalCache


def _cache(tmp_path: Path) -> LocalCache:
    def download(key: str, dest: Path) -> None:
        dest.write_bytes(f"payload:{key}".encode())

    return LocalCache(tmp_path, download=download)


def test_preview_fingerprint_changes_with_layout() -> None:
    rows = [
        {
            "page": 1,
            "rotation": 0.0,
            "left_margin": 0.0,
            "right_margin": 100.0,
            "top": 10.0,
            "bottom": 20.0,
            "tags": "Flute",
            "label": "",
        }
    ]
    breaks = {"Flute": []}
    spacings = {"Flute": 0.1}
    combined: list[str] = []

    first = LocalCache.preview_fingerprint(rows, breaks, spacings, combined)
    second = LocalCache.preview_fingerprint(rows, breaks, spacings, combined)
    assert first == second

    spacings_changed = {"Flute": 0.2}
    third = LocalCache.preview_fingerprint(rows, breaks, spacings_changed, combined)
    assert third != first


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


def test_write_preview_publishes_complete_dir(tmp_path: Path) -> None:
    cache = _cache(tmp_path)
    segments = tmp_path / "segments"
    segments.mkdir()
    (segments / "s0.png").write_bytes(b"seg0")
    (segments / "s1.png").write_bytes(b"seg1")

    cache.write_preview("ps1", "fp123", segments)
    preview = cache.preview_dir("ps1")

    assert preview.is_dir()
    assert (preview / ".fingerprint").read_text() == "fp123"
    assert (preview / "s0.png").read_bytes() == b"seg0"
    assert (preview / "s1.png").read_bytes() == b"seg1"


def test_page_image_url_includes_png_suffix() -> None:
    from app.services.segments import page_image_url

    assert page_image_url("priv1", 3, "lowres") == "/api/v1/partsets/priv1/page-image/3.png?res=lowres"


def test_write_preview_replaces_existing_files(tmp_path: Path) -> None:
    cache = _cache(tmp_path)
    preview = cache.preview_dir("ps1")
    preview.mkdir(parents=True)
    (preview / "s0.png").write_bytes(b"old")
    (preview / ".fingerprint").write_text("old-fp")

    segments = tmp_path / "segments"
    segments.mkdir()
    (segments / "s0.png").write_bytes(b"new")

    cache.write_preview("ps1", "new-fp", segments)

    assert (preview / "s0.png").read_bytes() == b"new"
    assert (preview / ".fingerprint").read_text() == "new-fp"
