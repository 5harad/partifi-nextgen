"""Clear and set partset failure metadata for the progress UI."""

from __future__ import annotations

from datetime import datetime

from app.models import Partset

MAX_ERROR_MESSAGE_LEN = 512


def mark_partset_failure(
    partset: Partset,
    stage: str,
    *,
    message: str | None = None,
) -> None:
    if partset.parts_ready:
        return
    partset.error = stage
    partset.error_message = _truncate_error_message(message)
    partset.error_ts = datetime.utcnow()


def _truncate_error_message(message: str | None) -> str | None:
    if message is None:
        return None
    normalized = " ".join(str(message).split())
    if len(normalized) <= MAX_ERROR_MESSAGE_LEN:
        return normalized
    return normalized[: MAX_ERROR_MESSAGE_LEN - 3] + "..."


def clear_partset_failure(partset: Partset) -> None:
    partset.error = None
    partset.error_message = None
    partset.error_ts = None
    partset.last_job_id = None
