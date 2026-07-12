"""Reuse score-level page/segment analysis across partsets."""

from __future__ import annotations

import db_conn


def score_analysis_complete(score_id: str) -> bool:
    row = db_conn.fetchone(
        "SELECT analysis_complete FROM scores WHERE id = :id",
        {"id": score_id},
    )
    return bool(row and row.analysis_complete)


def invalidate_score_analysis(score_id: str) -> None:
    db_conn.execute(
        "DELETE FROM original_segments WHERE score_id = :score_id",
        {"score_id": score_id},
    )
    db_conn.execute(
        "DELETE FROM original_pages WHERE score_id = :score_id",
        {"score_id": score_id},
    )
    db_conn.execute(
        "UPDATE scores SET analysis_start = NULL, analysis_complete = NULL WHERE id = :id",
        {"id": score_id},
    )


def fetch_score_orientation(score_id: str) -> str:
    row = db_conn.fetchone(
        "SELECT orientation FROM scores WHERE id = :id",
        {"id": score_id},
    )
    if not row or not row.orientation:
        return "portrait"
    return str(row.orientation)


def copy_score_segs_to_partset(score_id: str, partset_id: str) -> None:
    db_conn.execute(
        "DELETE FROM segments WHERE partset_id = :partset_id",
        {"partset_id": partset_id},
    )
    db_conn.execute(
        "DELETE FROM pages WHERE partset_id = :partset_id",
        {"partset_id": partset_id},
    )
    db_conn.execute(
        "INSERT INTO segments (partset_id, page, top, bottom) "
        "SELECT :partset_id, page, top, bottom FROM original_segments WHERE score_id = :score_id",
        {"partset_id": partset_id, "score_id": score_id},
    )
    db_conn.execute(
        "INSERT INTO pages (partset_id, page, left_margin, right_margin, rotation) "
        "SELECT :partset_id, page, left_margin, right_margin, rotation "
        "FROM original_pages WHERE score_id = :score_id",
        {"partset_id": partset_id, "score_id": score_id},
    )
    db_conn.execute(
        "UPDATE partsets SET status = 'analysis', analysis_progress = 100, "
        "analysis_start = NOW(), analysis_complete = NOW() WHERE id = :id",
        {"id": partset_id},
    )


def copy_partset_segs_to_score(partset_id: str, score_id: str) -> None:
    db_conn.execute(
        "DELETE FROM original_segments WHERE score_id = :score_id",
        {"score_id": score_id},
    )
    db_conn.execute(
        "INSERT INTO original_segments (score_id, page, top, bottom) "
        "SELECT :score_id, page, top, bottom FROM segments WHERE partset_id = :partset_id",
        {"score_id": score_id, "partset_id": partset_id},
    )
    db_conn.execute(
        "DELETE FROM original_pages WHERE score_id = :score_id",
        {"score_id": score_id},
    )
    db_conn.execute(
        "INSERT INTO original_pages (score_id, page, left_margin, right_margin, rotation) "
        "SELECT :score_id, page, left_margin, right_margin, rotation FROM pages WHERE partset_id = :partset_id",
        {"score_id": score_id, "partset_id": partset_id},
    )
    db_conn.execute(
        "UPDATE scores SET "
        "analysis_start = (SELECT analysis_start FROM partsets WHERE id = :partset_id), "
        "analysis_complete = NOW(), "
        "num_pages = (SELECT COUNT(*) FROM original_pages WHERE score_id = :score_id) "
        "WHERE id = :score_id",
        {"partset_id": partset_id, "score_id": score_id},
    )
