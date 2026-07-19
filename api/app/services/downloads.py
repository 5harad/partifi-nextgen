"""Browser-facing download URLs and part download tracking."""

from __future__ import annotations

from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Part, Partset
from app.models.tables import Download
from app.utils.strings import tag_to_filename
from pipeline.part_filenames import MAX_PART_FILENAME_LEN, resolve_part_filename


def score_pdf_url_for_score(score_id: str) -> str:
    return f"/api/v1/scores/{score_id}/score.pdf"


def score_pdf_url_for_access(access_id: str) -> str:
    return f"/api/v1/access/{access_id}/score.pdf"


def score_pdf_url_for_owner(private_id: str) -> str:
    return f"/api/v1/partsets/{private_id}/score.pdf"


def part_file_url(partset: Partset, filename: str, *, mode: str = "public") -> str:
    encoded = quote(filename, safe="")
    if mode == "owner" and partset.private_id:
        return f"/api/v1/partsets/{partset.private_id}/part-file/{encoded}"
    return f"/api/v1/access/{partset.id}/part-file/{encoded}"


def partgen_redirect_url(access_id: str, tag: str, page_size: str) -> str:
    """Frontend partgen route carrying stable part identity, not a stale URL."""
    if page_size not in {"letter", "a4"}:
        raise ValueError("page_size must be letter or a4")
    return f"/{access_id}/partgen?{urlencode({'part': tag, 'format': page_size})}"


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


def browser_part_filename(partset_id: str, filename: str) -> str | None:
    """Return the friendly downloaded name without the internal partset prefix."""
    parsed = part_file_name_from_download_filename(partset_id, filename)
    if not parsed:
        return None
    stored_name, is_a4 = parsed
    stem = stored_name.removesuffix(".pdf") or "part"
    return f"{stem}-a4.pdf" if is_a4 else f"{stem}.pdf"


def _find_part_for_download(db: Session, partset: Partset, stored_name: str) -> Part | None:
    part = (
        db.query(Part)
        .filter(Part.partset_id == partset.id, Part.file_name == stored_name)
        .first()
    )
    if part is not None:
        return part
    if len(stored_name) <= MAX_PART_FILENAME_LEN:
        return None
    for candidate in (
        db.query(Part)
        .filter(Part.partset_id == partset.id, Part.combined.is_(True))
        .all()
    ):
        if stored_name == tag_to_filename(candidate.tag):
            return candidate
    return None


def resolve_part_cache_filename(
    db: Session,
    partset: Partset,
    filename: str,
) -> str | None:
    """Map a served download filename to a filesystem-safe cache key."""
    parsed = part_file_name_from_download_filename(partset.id, filename)
    if not parsed:
        return None
    stored_name, is_a4 = parsed
    part = _find_part_for_download(db, partset, stored_name)
    if part is None:
        if len(stored_name) > MAX_PART_FILENAME_LEN:
            return None
        return filename

    resolved = resolve_part_filename(
        part.file_name or "",
        part.tag,
        combined=bool(part.combined),
    )
    prefix = f"{partset.id}_a4_" if is_a4 else f"{partset.id}_"
    return f"{prefix}{resolved}"


def safe_cached_part_path(cache, partset_id: str, filename: str):
    """Return cached part path, or None if missing or the filename is too long for the filesystem."""
    try:
        return cache.ensure_part_file(partset_id, filename)
    except OSError as exc:
        if exc.errno == 36:
            return None
        raise


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
