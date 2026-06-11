"""Browser-facing download URLs served via the API (not presigned S3)."""

from __future__ import annotations

from app.models import Partset


def score_pdf_url_for_score(score_id: str) -> str:
    return f"/api/v1/scores/{score_id}/score.pdf"


def score_pdf_url_for_access(access_id: str) -> str:
    return f"/api/v1/access/{access_id}/score-pdf"


def score_pdf_url_for_owner(private_id: str) -> str:
    return f"/api/v1/partsets/{private_id}/score-pdf"


def part_file_url(partset: Partset, filename: str, *, mode: str = "public") -> str:
    if mode == "owner" and partset.private_id:
        return f"/api/v1/partsets/{partset.private_id}/part-file/{filename}"
    return f"/api/v1/access/{partset.id}/part-file/{filename}"


def score_pdf_url_for_partset(partset: Partset, *, mode: str = "public") -> str | None:
    if not partset.score_id:
        return None
    if mode == "owner" and partset.private_id:
        return score_pdf_url_for_owner(partset.private_id)
    return score_pdf_url_for_access(partset.id)
