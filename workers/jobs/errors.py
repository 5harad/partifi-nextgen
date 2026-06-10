"""Mark partset pipeline failures for the progress UI."""

from __future__ import annotations

import db_conn

ERROR_STAGES = frozenset({"import", "convert", "analysis", "cut", "paste"})


def mark_partset_error(partset_id: str, stage: str | None = None) -> None:
    if stage is None:
        row = db_conn.fetchone(
            "SELECT status FROM partsets WHERE id = :id",
            {"id": partset_id},
        )
        stage = row.status if row and row.status in ERROR_STAGES else "import"
    elif stage not in ERROR_STAGES:
        stage = "import"

    db_conn.execute(
        "UPDATE partsets SET error = :stage WHERE id = :id",
        {"stage": stage, "id": partset_id},
    )
