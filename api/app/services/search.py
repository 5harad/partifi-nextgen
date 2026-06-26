"""Public library search over partsets."""

from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.services.downloads import score_pdf_url_for_score

_MAX_RAW_ROWS = 500
_MAX_RESULTS = 100

_APOSTROPHE_RE = re.compile(r"[''\u2019]")
_DOUBLE_QUOTE_RE = re.compile(r'["\u201c\u201d]')
_TOKEN_EDGE_RE = re.compile(r"^[\W_]+|[\W_]+$", re.UNICODE)
_BOOLEAN_OPERATOR_PREFIX_RE = re.compile(r"^[-+~><]+")


def _clean_token_part(part: str) -> str:
    part = _BOOLEAN_OPERATOR_PREFIX_RE.sub("", part)
    part = part.rstrip("*")
    return _TOKEN_EDGE_RE.sub("", part)


def _expand_fts_tokens(raw: str) -> list[str]:
    token = _TOKEN_EDGE_RE.sub("", raw)
    if not token:
        return []
    tokens: list[str] = []
    for part in _APOSTROPHE_RE.split(token):
        cleaned = _clean_token_part(part)
        if len(cleaned) >= 2 and not cleaned.isnumeric():
            tokens.append(cleaned)
    return tokens


def build_boolean_fulltext_query(query: str) -> str:
    normalized = _DOUBLE_QUOTE_RE.sub(" ", query)
    processed: list[str] = []
    for raw in normalized.split():
        for token in _expand_fts_tokens(raw):
            processed.append(f"+{token}*")
    return " ".join(processed)


def search_partsets(db: Session, query: str) -> list[dict]:
    q = query.strip()
    if not q:
        return []

    boolean_q = build_boolean_fulltext_query(q)
    if not boolean_q:
        return []

    try:
        rows = db.execute(
            text(
                """
                SELECT p.id, p.score_id, p.imslp_id, p.title, p.composer, p.publisher
                FROM partsets p
                JOIN scores s ON s.id = p.score_id
                WHERE MATCH (p.title, p.composer, p.publisher, p.imslp_id) AGAINST (:q IN BOOLEAN MODE)
                  AND p.copyright = 'before 1923'
                  AND p.analysis_complete IS NOT NULL
                  AND s.s3 = 1
                  AND s.file_size > 0
                ORDER BY p.num_downloads DESC
                LIMIT :limit
                """
            ),
            {"q": boolean_q, "limit": _MAX_RAW_ROWS},
        ).mappings()
    except ProgrammingError as exc:
        if exc.orig and getattr(exc.orig, "args", None) and exc.orig.args[0] == 1064:
            return []
        raise

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
