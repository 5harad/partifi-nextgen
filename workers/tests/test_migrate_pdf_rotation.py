"""Tests for legacy PDF rotation migration configuration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.migrate_pdf_rotation import (
    CONFIRMED_PARTSET_ROTATIONS,
    _download_score_pdf,
    main,
)


def test_confirmed_candidates_use_internal_partset_ids_and_actual_metadata() -> None:
    assert CONFIRMED_PARTSET_ROTATIONS == {
        "jigmi-xqpek": 270,
        "dliol-bejej": 270,
    }


def test_apply_requires_viewer_validation() -> None:
    with patch("sys.argv", ["migrate_pdf_rotation.py", "--apply"]):
        with pytest.raises(SystemExit, match="2"):
            main()


def test_dry_run_download_uses_scratch_path(tmp_path: Path) -> None:
    with patch("scripts.migrate_pdf_rotation.download_file") as download:
        score_pdf = _download_score_pdf("score-1", tmp_path)

    assert score_pdf == tmp_path / "score.pdf"
    download.assert_called_once_with("scores/score-1_score.pdf", score_pdf)
