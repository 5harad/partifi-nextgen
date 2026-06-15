from unittest.mock import MagicMock, patch

from jobs import imslp_import


def test_run_imslp_import_reuses_existing_score_without_download() -> None:
    existing = MagicMock(id="abc12")
    with (
        patch.object(imslp_import, "_existing_score_for_imslp", return_value=existing),
        patch.object(imslp_import, "download_imslp_pdf") as download,
        patch.object(imslp_import, "_attach_score_and_run_pipeline") as attach,
        patch.object(imslp_import, "_set_import_progress") as progress,
        patch.object(imslp_import, "release_import_lock"),
        patch.object(imslp_import.shutil, "rmtree"),
        patch.object(imslp_import.Path, "mkdir"),
        patch.object(imslp_import.Path, "exists", return_value=False),
    ):
        imslp_import.run_imslp_import("part01", "33421", job_id="job1")

    download.assert_not_called()
    progress.assert_called_once_with("part01", 100.0)
    attach.assert_called_once_with("part01", "abc12", job_id="job1")
