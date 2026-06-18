"""Score PDF availability checks shared by API and workers."""

from __future__ import annotations

from datetime import datetime


def score_has_archived_pdf(*, s3: bool, file_size: int | None) -> bool:
    """True when the score row points at a durable S3 PDF."""
    return bool(s3) and int(file_size or 0) > 0


def score_ready_for_reuse(
    *,
    convert_complete: datetime | None,
    num_pages: int | None,
) -> bool:
    """True when a score PDF has been converted successfully at least once."""
    return convert_complete is not None and int(num_pages or 0) >= 1
