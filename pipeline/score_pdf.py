"""Score PDF availability checks shared by API and workers."""

from __future__ import annotations


def score_has_archived_pdf(*, s3: bool, file_size: int | None) -> bool:
    """True when the score row points at a durable S3 PDF."""
    return bool(s3) and int(file_size or 0) > 0
