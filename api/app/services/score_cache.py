"""Reuse score-level segment analysis when cloning partsets in the API."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Partset, Score


def score_analysis_complete(db: Session, score_id: str) -> bool:
    score = db.get(Score, score_id)
    return bool(score and score.analysis_complete)


def copy_score_segs_to_partset(db: Session, score_id: str, partset_id: str) -> None:
    db.execute(text("DELETE FROM segments WHERE partset_id = :partset_id"), {"partset_id": partset_id})
    db.execute(text("DELETE FROM pages WHERE partset_id = :partset_id"), {"partset_id": partset_id})
    db.execute(
        text(
            "INSERT INTO segments (partset_id, page, top, bottom) "
            "SELECT :partset_id, page, top, bottom FROM original_segments WHERE score_id = :score_id"
        ),
        {"partset_id": partset_id, "score_id": score_id},
    )
    db.execute(
        text(
            "INSERT INTO pages (partset_id, page, left_margin, right_margin, rotation) "
            "SELECT :partset_id, page, left_margin, right_margin, rotation "
            "FROM original_pages WHERE score_id = :score_id"
        ),
        {"partset_id": partset_id, "score_id": score_id},
    )


def mark_import_pipeline_complete(db: Session, partset: Partset, score: Score) -> None:
    now = datetime.utcnow()
    partset.score_id = score.id
    partset.status = "analysis"
    partset.import_start = partset.import_start or now
    partset.import_complete = now
    partset.import_progress = 100.0
    partset.convert_start = score.convert_complete or now
    partset.convert_complete = score.convert_complete or now
    partset.convert_progress = 100.0 if score.convert_complete else 0.0
    partset.analysis_start = score.analysis_start or now
    partset.analysis_complete = score.analysis_complete or now
    partset.analysis_progress = 100.0 if score.analysis_complete else 0.0
