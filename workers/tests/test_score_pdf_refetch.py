from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from pipeline.pdf_validate import PDF_CORRUPT_MESSAGE
from score_pdf_refetch import repair_corrupt_score_pdf, replace_score_pdf_from_imslp


def _score_row(**overrides):
    base = {
        "id": "abc12",
        "imslp_id": "266246",
        "file_size": 1000,
        "file_hash": "oldhash",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_replace_uploads_when_hash_differs(tmp_path: Path) -> None:
    dest = tmp_path / "score.pdf"
    workdir = tmp_path / "work"
    workdir.mkdir()

    def _download(_imslp_id, path, **_kwargs):
        path.write_bytes(b"%PDF-new-bytes")
        return path.stat().st_size

    cache = MagicMock()
    with (
        patch("score_pdf_refetch._fetch_score", return_value=_score_row()),
        patch("score_pdf_refetch.download_imslp_pdf", side_effect=_download),
        patch("score_pdf_refetch.ensure_valid_score_pdf"),
        patch("score_pdf_refetch.infer_orientation_from_pdf", return_value="landscape"),
        patch("score_pdf_refetch.upload_file") as upload,
        patch("score_pdf_refetch.db_conn.execute") as execute,
        patch("score_pdf_refetch.invalidate_score_analysis") as invalidate,
        patch("score_pdf_refetch.get_local_cache", return_value=cache),
    ):
        assert replace_score_pdf_from_imslp("abc12", dest, workdir) is True

    upload.assert_called_once()
    execute.assert_called_once()
    invalidate.assert_called_once_with("abc12")
    cache.invalidate_score.assert_called_once_with("abc12")


def test_replace_skips_upload_when_hash_unchanged_unless_forced(tmp_path: Path) -> None:
    dest = tmp_path / "score.pdf"
    workdir = tmp_path / "work"
    workdir.mkdir()
    body = b"%PDF-same-bytes"

    def _download(_imslp_id, path, **_kwargs):
        path.write_bytes(body)
        return len(body)

    import hashlib

    same_hash = hashlib.sha1(body).hexdigest()
    cache = MagicMock()
    with (
        patch("score_pdf_refetch._fetch_score", return_value=_score_row(file_hash=same_hash)),
        patch("score_pdf_refetch.download_imslp_pdf", side_effect=_download),
        patch("score_pdf_refetch.ensure_valid_score_pdf"),
        patch("score_pdf_refetch.infer_orientation_from_pdf", return_value="portrait"),
        patch("score_pdf_refetch.upload_file") as upload,
        patch("score_pdf_refetch.db_conn.execute"),
        patch("score_pdf_refetch.invalidate_score_analysis"),
        patch("score_pdf_refetch.get_local_cache", return_value=cache),
    ):
        with pytest.raises(ValueError, match=PDF_CORRUPT_MESSAGE):
            replace_score_pdf_from_imslp("abc12", dest, workdir, force_replace=False)
        upload.assert_not_called()

        assert (
            replace_score_pdf_from_imslp(
                "abc12",
                dest,
                workdir,
                force_replace=True,
            )
            is True
        )
        upload.assert_called_once()


def test_repair_corrupt_requires_imslp_id(tmp_path: Path) -> None:
    dest = tmp_path / "score.pdf"
    workdir = tmp_path / "work"
    workdir.mkdir()
    with patch(
        "score_pdf_refetch._fetch_score",
        return_value=_score_row(imslp_id=None),
    ):
        with pytest.raises(ValueError, match=PDF_CORRUPT_MESSAGE):
            repair_corrupt_score_pdf("abc12", dest, workdir)


def test_repair_corrupt_delegates_to_replace(tmp_path: Path) -> None:
    dest = tmp_path / "score.pdf"
    workdir = tmp_path / "work"
    workdir.mkdir()
    with (
        patch("score_pdf_refetch._fetch_score", return_value=_score_row()),
        patch("score_pdf_refetch.replace_score_pdf_from_imslp") as replace,
    ):
        assert repair_corrupt_score_pdf("abc12", dest, workdir) is dest
    replace.assert_called_once_with(
        "abc12",
        dest,
        workdir,
        imslp_id="266246",
        force_replace=False,
    )
