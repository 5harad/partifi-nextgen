import hashlib
from unittest.mock import MagicMock, patch

from app.models import Score
from app.services.imslp_pdf import ingest_imslp_pdf_bytes

VALID_PDF = (
    b"%PDF-1.4\n"
    + b"x" * 2000
    + b"\nstartxref\n0\n%%EOF\n"
)
FILE_HASH = hashlib.sha1(VALID_PDF).hexdigest()


def test_ingest_reuploads_when_archived_pdf_invalid() -> None:
    existing = Score(
        id="abc12",
        file_hash=FILE_HASH,
        file_size=len(VALID_PDF),
        s3=True,
        num_downloads=0,
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = existing

    with (
        patch("app.services.imslp_pdf._archived_score_pdf_valid", return_value=False),
        patch("app.services.imslp_pdf.upload_bytes") as upload,
    ):
        score_id, action = ingest_imslp_pdf_bytes(db, "263659", VALID_PDF)

    assert score_id == "abc12"
    assert action == "continue"
    upload.assert_called_once()
    assert existing.file_hash == FILE_HASH


def test_ingest_skips_upload_when_archived_pdf_valid() -> None:
    existing = Score(
        id="abc12",
        file_hash=FILE_HASH,
        file_size=len(VALID_PDF),
        s3=True,
        num_downloads=0,
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = existing

    with (
        patch("app.services.imslp_pdf._archived_score_pdf_valid", return_value=True),
        patch("app.services.imslp_pdf.upload_bytes") as upload,
    ):
        score_id, action = ingest_imslp_pdf_bytes(db, "263659", VALID_PDF)

    assert score_id == "abc12"
    assert action == "continue"
    upload.assert_not_called()
