"""Public library search over partsets."""

from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.downloads import score_pdf_url_for_score

_MAX_RAW_ROWS = 500
_MAX_RESULTS = 100


def build_boolean_fulltext_query(query: str) -> str:
    exact_phrases = re.findall(r'".*?"', query)
    nonquoted = re.sub(r'".*?"', "", query)
    tokens = nonquoted.split()
    processed: list[str] = []
    for token in tokens:
        if len(token) >= 2 and not token.isnumeric():
            if not token.startswith(("+", "-")):
                token = f"+{token}"
            if not token.startswith("-") and not token.endswith("*"):
                token = f"{token}*"
        processed.append(token)
    return " ".join(exact_phrases + processed).strip()


def search_partsets(db: Session, query: str) -> list[dict]:
    q = query.strip()
    if not q:
        return []

    boolean_q = build_boolean_fulltext_query(q)
    if not boolean_q:
        return []

    rows = db.execute(
        text(
            """
            SELECT id, score_id, imslp_id, title, composer, publisher
            FROM partsets
            WHERE MATCH (title, composer, publisher, imslp_id) AGAINST (:q IN BOOLEAN MODE)
              AND copyright = 'before 1923'
              AND analysis_complete IS NOT NULL
            ORDER BY num_downloads DESC
            LIMIT :limit
            """
        ),
        {"q": boolean_q, "limit": _MAX_RAW_ROWS},
    ).mappings()

    results: list[dict] = []
    seen_scores: set[str] = set()
    for row in rows:
        score_id = row["score_id"]
        if not score_id or score_id in seen_scores:
            continue
        seen_scores.add(score_id)
        results.append(
            {
                "public_id": row["id"],
                "score_id": score_id,
                "imslp_id": row["imslp_id"],
                "title": row["title"],
                "composer": row["composer"],
                "publisher": row["publisher"],
                "score_pdf_url": score_pdf_url_for_score(score_id),
            }
        )
        if len(results) >= _MAX_RESULTS:
            break

    return results
