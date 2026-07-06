from unittest.mock import MagicMock, patch

from jobs import imslp_import


def test_resolve_imslp_id_persists_normalized_value() -> None:
    with patch.object(imslp_import.db_conn, "execute") as execute:
        result = imslp_import._resolve_imslp_id(
            "B3yzC",
            "https://imslp.org/wiki/Special:ImagefromIndex/282358/neo",
        )
    assert result == "282358"
    execute.assert_called_once_with(
        "UPDATE partsets SET imslp_id = :imslp_id WHERE id = :id",
        {"imslp_id": "282358", "id": "B3yzC"},
    )


def test_run_imslp_import_normalizes_legacy_url_before_download() -> None:
    existing = MagicMock(id="abc12")
    legacy_url = "https://imslp.org/wiki/Special:ImagefromIndex/282358/neo"
    with (
        patch.object(imslp_import, "_resolve_imslp_id", return_value="282358") as resolve,
        patch.object(imslp_import, "_existing_score_for_imslp", return_value=existing),
        patch.object(imslp_import, "download_imslp_pdf") as download,
        patch.object(imslp_import, "_attach_score_and_run_pipeline") as attach,
        patch.object(imslp_import, "_set_import_progress"),
        patch.object(imslp_import, "release_import_lock"),
        patch.object(imslp_import.shutil, "rmtree"),
        patch.object(imslp_import.Path, "mkdir"),
        patch.object(imslp_import.Path, "exists", return_value=False),
    ):
        imslp_import.run_imslp_import("B3yzC", legacy_url, job_id="job1")

    resolve.assert_called_once_with("B3yzC", legacy_url)
    download.assert_not_called()
    attach.assert_called_once_with("B3yzC", "abc12", job_id="job1")


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
