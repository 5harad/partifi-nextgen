"""Idempotent part row creation (MySQL upsert with SQLite fallback for tests)."""

from __future__ import annotations

from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

from app.models import Part


def upsert_part_row(
    db: Session,
    *,
    partset_id: str,
    tag: str,
    spacing: float,
    combined: bool,
    file_name: str,
    update_on_duplicate: bool = False,
) -> Part:
    """Insert a parts row or no-op / update when (partset_id, tag) already exists."""
    bind = db.get_bind()
    if bind.dialect.name == "mysql":
        stmt = mysql_insert(Part).values(
            partset_id=partset_id,
            tag=tag,
            spacing=spacing,
            combined=combined,
            file_name=file_name,
        )
        if update_on_duplicate:
            stmt = stmt.on_duplicate_key_update(
                spacing=spacing,
                combined=combined,
                file_name=file_name,
            )
        else:
            stmt = stmt.on_duplicate_key_update(partset_id=stmt.inserted.partset_id)
        db.execute(stmt)
        db.flush()
        part = (
            db.query(Part)
            .filter(Part.partset_id == partset_id, Part.tag == tag)
            .with_for_update()
            .first()
        )
        if part is not None:
            return part
        # Upsert succeeded but RR snapshot may hide the row; return a detached stub
        # so sync can track the tag without re-inserting on commit.
        return Part(
            partset_id=partset_id,
            tag=tag,
            spacing=spacing,
            combined=combined,
            file_name=file_name,
        )

    existing = (
        db.query(Part)
        .filter(Part.partset_id == partset_id, Part.tag == tag)
        .first()
    )
    if existing:
        if update_on_duplicate:
            existing.spacing = spacing
            existing.combined = combined
            existing.file_name = file_name
        return existing
    part = Part(
        partset_id=partset_id,
        tag=tag,
        spacing=spacing,
        combined=combined,
        file_name=file_name,
    )
    db.add(part)
    db.flush()
    return part
