"""Mark partset pipeline failures for the progress UI."""

from __future__ import annotations

import db_conn

ERROR_STAGES = frozenset({"import", "import_size", "convert", "analysis", "cut", "paste"})


def mark_partset_error(partset_id: str, stage: str | None = None) -> None:
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
        "UPDATE partsets SET error = :stage WHERE id = :id AND parts_ready = 0",
        {"stage": stage, "id": partset_id},
    )
