"""Tests for legacy PDF rotation migration configuration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts.migrate_pdf_rotation import (
    APPROVED_PARTSET_IDS,
    APPROVED_ROTATION_SEQUENCES,
    _download_score_pdf,
    _sibling_is_inert,
    main,
)


def test_only_viewer_validated_candidates_are_preapproved() -> None:
    assert APPROVED_PARTSET_IDS == {
        "dsbmc-wmhka",
        "qbccm-ogcoz",
        "blbfw-frboc",
        "efibz-itxmb",
    }
    assert APPROVED_ROTATION_SEQUENCES["dsbmc-wmhka"] == (270,) * 12 + (90,) * 2


def test_partset_is_required() -> None:
    with patch("sys.argv", ["migrate_pdf_rotation.py"]):
        with pytest.raises(SystemExit, match="2"):
            main()


def test_apply_requires_viewer_validation() -> None:
    with patch(
        "sys.argv",
        ["migrate_pdf_rotation.py", "--partset", "new-partset", "--apply"],
    ):
        with pytest.raises(SystemExit, match="2"):
            main()


def test_apply_requires_approved_candidate() -> None:
    with patch(
        "sys.argv",
        ["migrate_pdf_rotation.py", "--partset", "new-partset", "--apply", "--viewer-validated"],
    ):
        with pytest.raises(SystemExit, match="2"):
            main()


def test_apply_requires_expected_rotation() -> None:
    with patch(
        "sys.argv",
        [
            "migrate_pdf_rotation.py",
            "--partset",
            "qbccm-ogcoz",
            "--apply",
            "--viewer-validated",
        ],
    ):
        with pytest.raises(SystemExit, match="2"):
            main()


def test_new_candidate_dry_run_does_not_assume_rotation() -> None:
    with (
        patch("sys.argv", ["migrate_pdf_rotation.py", "--partset", "new-partset"]),
        patch("scripts.migrate_pdf_rotation._migrate") as migrate,
    ):
        main()

    migrate.assert_called_once_with("new-partset", apply=False, expected_rotations=None)


def test_mixed_rotation_candidate_uses_approved_sequence() -> None:
    with (
        patch(
            "sys.argv",
            ["migrate_pdf_rotation.py", "--partset", "dsbmc-wmhka", "--apply", "--viewer-validated"],
        ),
        patch("scripts.migrate_pdf_rotation._migrate") as migrate,
    ):
        main()

    migrate.assert_called_once_with(
        "dsbmc-wmhka",
        apply=True,
        expected_rotations=(270,) * 12 + (90,) * 2,
    )


def test_inert_sibling_does_not_block_single_partset_migration() -> None:
    assert _sibling_is_inert(
        SimpleNamespace(rotation_degrees=0, parts_ready=None, last_job_id=None, status="analysis")
    )
    assert not _sibling_is_inert(
        SimpleNamespace(rotation_degrees=0, parts_ready=True, last_job_id=None, status="analysis")
    )
    assert not _sibling_is_inert(
        SimpleNamespace(rotation_degrees=90, parts_ready=None, last_job_id=None, status="analysis")
    )


def test_dry_run_download_uses_scratch_path(tmp_path: Path) -> None:
    with patch("scripts.migrate_pdf_rotation.download_file") as download:
        score_pdf = _download_score_pdf("score-1", tmp_path)

    assert score_pdf == tmp_path / "score.pdf"
    download.assert_called_once_with("scores/score-1_score.pdf", score_pdf)
