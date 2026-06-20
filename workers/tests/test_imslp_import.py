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


def test_ensure_archived_pdf_reuploads_when_s3_copy_invalid() -> None:
    workdir = MagicMock()
    pdf_path = MagicMock()
    with (
        patch.object(imslp_import.db_conn, "fetchone", return_value=MagicMock(s3=1)),
        patch.object(imslp_import, "download_file", side_effect=ValueError("corrupt")),
        patch.object(imslp_import, "upload_file") as upload,
        patch.object(imslp_import.db_conn, "execute") as execute,
    ):
        imslp_import._ensure_archived_pdf("abc12", pdf_path, workdir)

    upload.assert_called_once()
    execute.assert_called_once()


def test_ensure_archived_pdf_skips_upload_when_s3_copy_valid() -> None:
    workdir = MagicMock()
    pdf_path = MagicMock()
    with (
        patch.object(imslp_import.db_conn, "fetchone", return_value=MagicMock(s3=1)),
        patch.object(imslp_import, "download_file"),
        patch.object(imslp_import, "ensure_valid_score_pdf"),
        patch.object(imslp_import, "upload_file") as upload,
        patch.object(imslp_import.db_conn, "execute") as execute,
    ):
        imslp_import._ensure_archived_pdf("abc12", pdf_path, workdir)

    upload.assert_not_called()
    execute.assert_not_called()
