from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

import pytest

from jobs import import_pipeline


@pytest.fixture(autouse=True)
def _no_import_lock_release():
    with patch.object(import_pipeline, "release_import_lock"):
        yield


def test_run_import_pipeline_reuses_warm_cache_and_analysis() -> None:
    workdir = Path("/tmp/partifi/test/import-job1")
    with (
        patch.object(import_pipeline, "_ensure_score_pdf", return_value=workdir / "score.pdf"),
        patch.object(import_pipeline, "infer_orientation_from_pdf", return_value="portrait"),
        patch.object(import_pipeline, "_fetch_score_import_state") as fetch_state,
        patch.object(import_pipeline, "_score_pages_available", return_value=True),
        patch.object(import_pipeline, "_run_convert") as run_convert,
        patch.object(import_pipeline, "_mark_convert_complete") as mark_convert,
        patch.object(import_pipeline, "score_analysis_complete", return_value=True),
        patch.object(import_pipeline, "copy_score_segs_to_partset") as copy_segs,
        patch.object(import_pipeline, "analyze_score"),
        patch.object(import_pipeline.db_conn, "execute"),
    ):
        fetch_state.return_value = SimpleNamespace(convert_complete="set", orientation="portrait")
        import_pipeline.run_import_pipeline("part01", "abc12", job_id="job1")

    run_convert.assert_not_called()
    mark_convert.assert_called_once()
    copy_segs.assert_called_once_with("abc12", "part01")


def test_run_import_pipeline_cold_cache_converts_without_reanalyze() -> None:
    workdir = Path("/tmp/partifi/test/import-job2")
    with (
        patch.object(import_pipeline, "_ensure_score_pdf", return_value=workdir / "score.pdf"),
        patch.object(import_pipeline, "infer_orientation_from_pdf", return_value="portrait"),
        patch.object(import_pipeline, "_fetch_score_import_state") as fetch_state,
        patch.object(import_pipeline, "_score_pages_available", return_value=False),
        patch.object(import_pipeline, "_run_convert") as run_convert,
        patch.object(import_pipeline, "score_analysis_complete", return_value=True),
        patch.object(import_pipeline, "copy_score_segs_to_partset") as copy_segs,
        patch.object(import_pipeline, "analyze_score") as analyze,
        patch.object(import_pipeline.db_conn, "execute"),
    ):
        fetch_state.return_value = SimpleNamespace(convert_complete="set", orientation="portrait")
        import_pipeline.run_import_pipeline("part01", "abc12", job_id="job1")

    run_convert.assert_called_once_with("part01", "abc12", ANY, workdir / "score.pdf", "portrait")
    copy_segs.assert_called_once()
    analyze.assert_not_called()


def test_run_import_pipeline_orientation_mismatch_invalidates_and_reconverts() -> None:
    workdir = Path("/tmp/partifi/test/import-job3")
    cache = MagicMock()
    with (
        patch.object(import_pipeline, "_ensure_score_pdf", return_value=workdir / "score.pdf"),
        patch.object(import_pipeline, "infer_orientation_from_pdf", return_value="landscape"),
        patch.object(import_pipeline, "_fetch_score_import_state") as fetch_state,
        patch.object(import_pipeline, "_score_pages_available", return_value=True),
        patch.object(import_pipeline, "_run_convert") as run_convert,
        patch.object(import_pipeline, "_mark_convert_complete"),
        patch.object(import_pipeline, "invalidate_score_analysis") as invalidate_analysis,
        patch.object(import_pipeline, "get_local_cache", return_value=cache),
        patch.object(import_pipeline, "score_analysis_complete", return_value=False),
        patch.object(import_pipeline, "ensure_lowres_files", return_value=[Path("page-1.png")]),
        patch.object(import_pipeline, "analyze_score") as analyze,
        patch.object(import_pipeline, "copy_partset_segs_to_score"),
        patch.object(import_pipeline.db_conn, "execute"),
    ):
        fetch_state.return_value = SimpleNamespace(convert_complete="set", orientation="portrait")
        import_pipeline.run_import_pipeline("part01", "abc12", job_id="job1")

    invalidate_analysis.assert_called_once_with("abc12")
    cache.invalidate_score_pages.assert_called_once_with("abc12")
    run_convert.assert_called_once_with("part01", "abc12", ANY, workdir / "score.pdf", "landscape")
    analyze.assert_called_once()


def test_ensure_score_pdf_repairs_via_imslp_refetch(tmp_path: Path) -> None:
    score_id = "abc12"
    workdir = tmp_path / "work"
    workdir.mkdir()
    cached = tmp_path / "cached.pdf"
    cached.write_bytes(b"%PDF-bad")
    repaired = workdir / "score.pdf"

    cache = MagicMock()
    cache.ensure_score_pdf.return_value = cached

    with (
        patch.object(import_pipeline, "get_local_cache", return_value=cache),
        patch.object(
            import_pipeline,
            "ensure_valid_score_pdf",
            side_effect=ValueError("corrupt"),
        ),
        patch.object(
            import_pipeline,
            "repair_corrupt_score_pdf",
            return_value=repaired,
        ) as repair,
    ):
        path = import_pipeline._ensure_score_pdf(score_id, workdir)

    assert path == repaired
    repair.assert_called_once_with(score_id, workdir / "score.pdf", workdir)


def test_ensure_score_pdf_no_imslp_repair_surfaces_corrupt(tmp_path: Path) -> None:
    score_id = "abc12"
    workdir = tmp_path / "work"
    workdir.mkdir()
    cached = tmp_path / "cached.pdf"
    cached.write_bytes(b"%PDF-bad")
    cache = MagicMock()
    cache.ensure_score_pdf.return_value = cached

    with (
        patch.object(import_pipeline, "get_local_cache", return_value=cache),
        patch.object(
            import_pipeline,
            "ensure_valid_score_pdf",
            side_effect=ValueError("corrupt"),
        ),
        patch.object(
            import_pipeline,
            "repair_corrupt_score_pdf",
            side_effect=ValueError("no imslp"),
        ),
        pytest.raises(ValueError, match="corrupt or incomplete"),
    ):
        import_pipeline._ensure_score_pdf(score_id, workdir)
