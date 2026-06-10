"""Personal library: favorites and saved partsets."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Favorite, Part, Partset
from app.services.partset_admin import resolve_partset_access
from app.services.s3 import presigned_get_url


def resolve_public_partset_id(db: Session, access_id: str) -> str | None:
    resolved = resolve_partset_access(db, access_id)
    if not resolved:
        return None
    partset, _mode = resolved
    return partset.id


def claim_partset_for_user(db: Session, partset: Partset, user_id: str) -> None:
    partset.user_id = user_id
    existing = (
        db.query(Favorite)
        .filter(Favorite.partset_id == partset.id, Favorite.user_id == user_id)
        .first()
    )
    if existing:
        existing.admin = True
        existing.ts = datetime.utcnow()
    else:
        db.add(
            Favorite(
                partset_id=partset.id,
                user_id=user_id,
                admin=True,
                ts=datetime.utcnow(),
            )
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

    items: list[dict] = []
    for favorite, partset in rows:
        parts_payload: list[dict] = []
        score_pdf_url = None
        if partset.parts_ready:
            parts = (
                db.query(Part)
                .filter(Part.partset_id == partset.id)
                .order_by(Part.combined, Part.tag)
                .all()
            )
            for part in parts:
                letter_name = f"{partset.id}_{part.file_name}"
                a4_name = f"{partset.id}_a4_{part.file_name}"
                parts_payload.append(
                    {
                        "tag": part.tag,
                        "file_name": part.file_name or "",
                        "letter_url": presigned_get_url(
                            f"parts/{partset.id}/{letter_name}",
                            download_name=letter_name,
                        ),
                        "a4_url": presigned_get_url(
                            f"parts/{partset.id}/{a4_name}",
                            download_name=a4_name,
                        ),
                    }
                )
        if partset.score_id:
            score_name = f"{partset.score_id}_score.pdf"
            score_pdf_url = presigned_get_url(
                f"scores/{partset.score_id}/score.pdf",
                download_name=score_name,
            )

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
        existing = (
            db.query(Favorite)
            .filter(Favorite.partset_id == partset.id, Favorite.user_id == user_id)
            .first()
        )
        if existing:
            existing.admin = existing.admin or admin
            existing.ts = datetime.utcnow()
        else:
            db.add(
                Favorite(
                    partset_id=partset.id,
                    user_id=user_id,
                    admin=admin,
                    ts=datetime.utcnow(),
                )
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
