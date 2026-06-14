"""Mark partset pipeline failures for the progress UI."""

from __future__ import annotations

import db_conn

ERROR_STAGES = frozenset({"import", "import_size", "convert", "analysis", "cut", "paste"})
MAX_ERROR_MESSAGE_LEN = 512


def truncate_error_message(message: str | None) -> str | None:
    if message is None:
        return None
    normalized = " ".join(str(message).split())
    if len(normalized) <= MAX_ERROR_MESSAGE_LEN:
        return normalized
    return normalized[: MAX_ERROR_MESSAGE_LEN - 3] + "..."


def partset_has_error(partset_id: str) -> bool:
    row = db_conn.fetchone(
        "SELECT error FROM partsets WHERE id = :id",
        {"id": partset_id},
    )
    return bool(row and row.error)


def mark_partset_error(
    partset_id: str,
    stage: str | None = None,
    *,
    message: str | None = None,
    job_id: str | None = None,
) -> None:
    row = db_conn.fetchone(
        "SELECT status, parts_ready FROM partsets WHERE id = :id",
        {"id": partset_id},
    )
    if row and row.parts_ready:
        return

    if stage is None:
        stage = row.status if row and row.status in ERROR_STAGES else "import"
    elif stage not in ERROR_STAGES:
        stage = "import"

    db_conn.execute(
        "UPDATE partsets SET error = :stage, error_message = :message, "
        "error_ts = NOW(), last_job_id = :job_id "
        "WHERE id = :id AND parts_ready = 0",
        {
            "stage": stage,
            "message": truncate_error_message(message),
            "job_id": str(job_id) if job_id is not None else None,
            "id": partset_id,
        },
    )
