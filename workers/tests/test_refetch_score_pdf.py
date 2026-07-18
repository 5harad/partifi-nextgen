from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import refetch_score_pdf


def test_refetch_score_pdf_stores_inferred_orientation_and_invalidates_analysis() -> None:
    score_id = "hMGHC"
    row = SimpleNamespace(id=score_id, imslp_id="12345", file_size=10, file_hash="abc")

    def _download_pdf(imslp_id, dest, **_kwargs):
        dest.write_bytes(b"%PDF-1.4\n")
        return 8

    with (
        patch.object(refetch_score_pdf, "_fetch_score", return_value=row),
        patch.object(refetch_score_pdf, "replace_score_pdf_from_imslp") as replace,
    ):
        refetch_score_pdf.refetch_score_pdf(score_id, dry_run=False)

    replace.assert_called_once()
    assert replace.call_args.kwargs["force_replace"] is True
    assert replace.call_args.kwargs["imslp_id"] == "12345"


def test_refetch_score_pdf_dry_run_skips_upload_and_db() -> None:
    score_id = "hMGHC"
    row = SimpleNamespace(id=score_id, imslp_id="12345", file_size=10, file_hash="abc")

    def _download_pdf(imslp_id, dest, **_kwargs):
        dest.write_bytes(b"%PDF-1.4\n%%EOF\n")
        return 16

    with (
        patch.object(refetch_score_pdf, "_fetch_score", return_value=row),
        patch.object(refetch_score_pdf, "download_imslp_pdf", side_effect=_download_pdf),
        patch.object(refetch_score_pdf, "ensure_valid_score_pdf"),
        patch.object(refetch_score_pdf, "infer_orientation_from_pdf", return_value="portrait"),
        patch.object(refetch_score_pdf, "replace_score_pdf_from_imslp") as replace,
    ):
        refetch_score_pdf.refetch_score_pdf(score_id, dry_run=True)

    replace.assert_not_called()
