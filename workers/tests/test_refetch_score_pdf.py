from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import refetch_score_pdf


def _download_pdf(_imslp_id: str, dest: Path) -> int:
    dest.write_bytes(b"%PDF-1.4")
    return 123


def test_refetch_score_pdf_stores_inferred_orientation_and_invalidates_analysis() -> None:
    score_id = "abc12"
    row = SimpleNamespace(imslp_id="IMSLP-1", file_size=100, file_hash="oldhash")
    cache = MagicMock()

    with (
        patch.object(refetch_score_pdf, "_fetch_score", return_value=row),
        patch.object(refetch_score_pdf, "download_imslp_pdf", side_effect=_download_pdf),
        patch.object(refetch_score_pdf, "ensure_valid_score_pdf"),
        patch.object(refetch_score_pdf, "validate_downloaded_pdf"),
        patch.object(refetch_score_pdf, "infer_orientation_from_pdf", return_value="landscape"),
        patch.object(refetch_score_pdf, "upload_file") as upload,
        patch.object(refetch_score_pdf.db_conn, "execute") as execute,
        patch.object(refetch_score_pdf, "invalidate_score_analysis") as invalidate_analysis,
        patch.object(refetch_score_pdf, "get_local_cache", return_value=cache),
    ):
        refetch_score_pdf.refetch_score_pdf(score_id, dry_run=False)

    upload.assert_called_once()
    execute.assert_called_once()
    params = execute.call_args.args[1]
    assert params["orientation"] == "landscape"
    invalidate_analysis.assert_called_once_with(score_id)
    cache.invalidate_score.assert_called_once_with(score_id)


def test_refetch_score_pdf_dry_run_skips_upload_and_db() -> None:
    score_id = "abc12"
    row = SimpleNamespace(imslp_id="IMSLP-1", file_size=100, file_hash="oldhash")

    with (
        patch.object(refetch_score_pdf, "_fetch_score", return_value=row),
        patch.object(refetch_score_pdf, "download_imslp_pdf", side_effect=_download_pdf),
        patch.object(refetch_score_pdf, "ensure_valid_score_pdf"),
        patch.object(refetch_score_pdf, "validate_downloaded_pdf"),
        patch.object(refetch_score_pdf, "infer_orientation_from_pdf", return_value="portrait"),
        patch.object(refetch_score_pdf, "upload_file") as upload,
        patch.object(refetch_score_pdf.db_conn, "execute") as execute,
        patch.object(refetch_score_pdf, "invalidate_score_analysis") as invalidate_analysis,
        patch.object(refetch_score_pdf, "get_local_cache") as get_cache,
    ):
        refetch_score_pdf.refetch_score_pdf(score_id, dry_run=True)

    upload.assert_not_called()
    execute.assert_not_called()
    invalidate_analysis.assert_not_called()
    get_cache.assert_not_called()
