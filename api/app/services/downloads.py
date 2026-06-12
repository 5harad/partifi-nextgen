"""Browser-facing download URLs and part download tracking."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Part, Partset
from app.models.tables import Download


def score_pdf_url_for_score(score_id: str) -> str:
    return f"/api/v1/scores/{score_id}/score.pdf"


def score_pdf_url_for_access(access_id: str) -> str:
    return f"/api/v1/access/{access_id}/score.pdf"


def score_pdf_url_for_owner(private_id: str) -> str:
    return f"/api/v1/partsets/{private_id}/score.pdf"


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


def part_file_name_from_download_filename(partset_id: str, filename: str) -> tuple[str, bool] | None:
    """Return (parts.file_name, is_a4) parsed from a served part PDF filename."""
    prefix = f"{partset_id}_"
    if not filename.startswith(prefix) or not filename.endswith(".pdf"):
        return None
    remainder = filename[len(prefix) :]
    if remainder.startswith("a4_"):
        return remainder[3:], True
    return remainder, False


def record_part_download(
    db: Session,
    partset: Partset,
    filename: str,
    *,
    user_id: str | None = None,
) -> None:
    parsed = part_file_name_from_download_filename(partset.id, filename)
    if not parsed:
        return

    file_name, is_a4 = parsed
    part = (
        db.query(Part)
        .filter(Part.partset_id == partset.id, Part.file_name == file_name)
        .first()
    )
    if not part:
        return

    tag = f"{part.tag}/a4" if is_a4 else part.tag
    for attempt in range(3):
        now = datetime.utcnow()
        if attempt:
            now += timedelta(seconds=attempt)
        db.add(
            Download(
                score_id=partset.score_id,
                partset_id=partset.id,
                tag=tag,
                user_id=user_id,
                bcookie=None,
                ts=now,
            )
        )
        partset.num_downloads = (partset.num_downloads or 0) + 1
        partset.last_access = now
        try:
            db.commit()
            return
        except IntegrityError:
            db.rollback()
            partset = db.get(Partset, partset.id) or partset
