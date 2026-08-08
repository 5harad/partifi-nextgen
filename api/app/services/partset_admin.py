from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Break, Page, Part, Partset, Segment
from app.services.local_cache import get_local_cache
from app.services.s3 import delete_prefix


def get_partset_by_public_id(db: Session, public_id: str) -> Partset | None:
    return db.query(Partset).filter(Partset.id == public_id).first()


def resolve_partset_access(db: Session, access_id: str) -> tuple[Partset, str] | None:
    """Resolve an access id to a partset and owner/public mode (private id wins on collision)."""
    by_private = db.query(Partset).filter(Partset.private_id == access_id).first()
    if by_private:
        return by_private, "owner"
    by_public = db.query(Partset).filter(Partset.id == access_id).first()
    if by_public:
        return by_public, "public"
    return None


COPYRIGHT_VALUES = frozenset({"before 1923", "after 1923", "unknown"})


def update_partset_metadata(
    db: Session,
    partset: Partset,
    *,
    title: str,
    composer: str,
    publisher: str,
    copyright: str,
) -> None:
    from app.services.preview import _partgen_in_progress

    copyright_value = copyright.strip()
    if copyright_value not in COPYRIGHT_VALUES:
        raise ValueError("Invalid copyright value")

    next_title = title.strip()
    next_composer = composer.strip()
    next_publisher = publisher.strip() or None
    # Only title/composer appear on generated part PDFs; publisher/copyright do not.
    identity_changed = (
        next_title != (partset.title or "")
        or next_composer != (partset.composer or "")
    )

    partset.title = next_title
    partset.composer = next_composer
    partset.publisher = next_publisher
    partset.copyright = copyright_value
    partset.mod_ts = datetime.utcnow()

    if not identity_changed:
        db.commit()
        return

    generation_in_progress = _partgen_in_progress(partset)
    partset.parts_ready = False
    if not generation_in_progress:
        partset.status = "analysis"
        partset.cut_start = None
        partset.cut_complete = None
        partset.cut_progress = 0.0
        partset.paste_start = None
        partset.paste_complete = None
        partset.paste_progress = 0.0
    get_local_cache().invalidate_parts(partset.id)
    db.commit()


def delete_partset(db: Session, partset: Partset) -> None:
    partset_id = partset.id
    db.query(Segment).filter(Segment.partset_id == partset_id).delete()
    db.query(Break).filter(Break.partset_id == partset_id).delete()
    db.query(Part).filter(Part.partset_id == partset_id).delete()
    db.query(Page).filter(Page.partset_id == partset_id).delete()
    db.execute(text("DELETE FROM favorites WHERE partset_id = :id"), {"id": partset_id})
    db.execute(text("DELETE FROM downloads WHERE partset_id = :id"), {"id": partset_id})
    db.delete(partset)
    db.commit()
    delete_prefix(f"parts/{partset_id}/")
    cache = get_local_cache()
    cache.invalidate_preview(partset_id)
    cache.invalidate_parts(partset_id)
