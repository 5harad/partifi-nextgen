"""Personal library: favorites and saved partsets."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

from app.models import Favorite, Part, Partset
from app.services.partset_admin import resolve_partset_access
from app.services.downloads import part_file_url, score_pdf_url_for_partset


def resolve_public_partset_id(db: Session, access_id: str) -> str | None:
    resolved = resolve_partset_access(db, access_id)
    if not resolved:
        return None
    partset, _mode = resolved
    return partset.id


def _upsert_favorite(
    db: Session,
    *,
    partset_id: str,
    user_id: str,
    admin: bool,
    ts: datetime,
) -> None:
    bind = db.get_bind()
    if bind.dialect.name == "mysql":
        stmt = mysql_insert(Favorite).values(
            partset_id=partset_id,
            user_id=user_id,
            admin=admin,
            ts=ts,
        ).on_duplicate_key_update(admin=admin, ts=ts)
        db.execute(stmt)
        return

    existing = (
        db.query(Favorite)
        .filter(Favorite.partset_id == partset_id, Favorite.user_id == user_id)
        .first()
    )
    if existing:
        existing.admin = admin
        existing.ts = ts
    else:
        db.add(
            Favorite(
                partset_id=partset_id,
                user_id=user_id,
                admin=admin,
                ts=ts,
            )
        )


def claim_partset_for_user(db: Session, partset: Partset, user_id: str) -> None:
    if partset.user_id is None:
        partset.user_id = user_id
    _upsert_favorite(
        db,
        partset_id=partset.id,
        user_id=user_id,
        admin=True,
        ts=datetime.utcnow(),
    )


def list_library(db: Session, user_id: str) -> list[dict]:
    rows = (
        db.query(Favorite, Partset)
        .join(Partset, Favorite.partset_id == Partset.id)
        .filter(
            Favorite.user_id == user_id,
            Partset.analysis_complete.isnot(None),
        )
        .order_by(Favorite.ts.desc())
        .all()
    )

    partset_ids = [partset.id for _, partset in rows]
    parts_by_partset: dict[str, list[Part]] = defaultdict(list)
    if partset_ids:
        all_parts = (
            db.query(Part)
            .filter(Part.partset_id.in_(partset_ids))
            .order_by(Part.partset_id, Part.combined, Part.tag)
            .all()
        )
        for part in all_parts:
            parts_by_partset[part.partset_id].append(part)

    items: list[dict] = []
    for favorite, partset in rows:
        link_mode = "owner" if favorite.admin and partset.private_id else "public"
        parts_payload: list[dict] = []
        for part in parts_by_partset.get(partset.id, []):
            letter_name = f"{partset.id}_{part.file_name}"
            a4_name = f"{partset.id}_a4_{part.file_name}"
            parts_payload.append(
                {
                    "tag": part.tag,
                    "file_name": part.file_name or "",
                    "letter_url": part_file_url(partset, letter_name, mode=link_mode),
                    "a4_url": part_file_url(partset, a4_name, mode=link_mode),
                }
            )
        score_pdf_url = score_pdf_url_for_partset(partset, mode=link_mode)

        items.append(
            {
                "partset_id": partset.id,
                "private_id": partset.private_id if favorite.admin else None,
                "score_id": partset.score_id,
                "title": partset.title,
                "composer": partset.composer,
                "publisher": partset.publisher,
                "admin": bool(favorite.admin),
                "parts_ready": bool(partset.parts_ready),
                "parts": parts_payload,
                "score_pdf_url": score_pdf_url,
            }
        )
    return items


def favorite_status(db: Session, user_id: str, access_id: str) -> bool:
    partset_id = resolve_public_partset_id(db, access_id)
    if not partset_id:
        return False
    favorite = (
        db.query(Favorite)
        .filter(Favorite.partset_id == partset_id, Favorite.user_id == user_id)
        .first()
    )
    if not favorite:
        return False

    resolved = resolve_partset_access(db, access_id)
    if resolved:
        partset, mode = resolved
        if mode == "owner" and not favorite.admin:
            favorite.admin = True
            db.commit()
    return True


def update_favorite(
    db: Session,
    user_id: str,
    access_id: str,
    *,
    action: str,
) -> None:
    resolved = resolve_partset_access(db, access_id)
    if not resolved:
        raise ValueError("Partset not found")
    partset, mode = resolved

    if action == "add":
        admin = mode == "owner"
        if admin:
            claim_partset_for_user(db, partset, user_id)
        else:
            _upsert_favorite(
                db,
                partset_id=partset.id,
                user_id=user_id,
                admin=False,
                ts=datetime.utcnow(),
            )
        db.commit()
        return

    if action == "remove":
        db.query(Favorite).filter(
            Favorite.partset_id == partset.id,
            Favorite.user_id == user_id,
        ).delete()
        db.commit()
        return

    raise ValueError("Invalid favorite action")
