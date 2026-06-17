"""Tests for idempotent part row upsert."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import Page, Part, Partset, Score, Segment
from app.services.part_rows import upsert_part_row
from app.services.segments import sync_part_rows_from_tags


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    now = datetime.now(UTC)

    session.add(
        Score(
            id="score1",
            num_pages=1,
            import_complete=now,
            convert_complete=now,
            analysis_complete=now,
        )
    )
    session.add(
        Partset(
            id="pub1",
            private_id="priv1",
            score_id="score1",
            parts_ready=True,
            status="analysis",
            import_complete=now,
            convert_complete=now,
            analysis_complete=now,
        )
    )
    session.add(Page(partset_id="pub1", page=1, left_margin=0, right_margin=100, rotation=0))
    session.commit()
    return session


def test_upsert_part_row_is_idempotent(db: Session) -> None:
    first = upsert_part_row(
        db,
        partset_id="pub1",
        tag="viola",
        spacing=0.1,
        combined=False,
        file_name="viola.pdf",
    )
    first.spacing = 0.5
    db.flush()

    second = upsert_part_row(
        db,
        partset_id="pub1",
        tag="viola",
        spacing=0.1,
        combined=False,
        file_name="viola.pdf",
    )
    assert second.tag == "viola"
    assert second.spacing == 0.5
    assert db.query(Part).filter(Part.partset_id == "pub1").count() == 1


def test_upsert_part_row_can_update_combined_part(db: Session) -> None:
    upsert_part_row(
        db,
        partset_id="pub1",
        tag="violin + viola",
        spacing=0.1,
        combined=False,
        file_name="violin_viola.pdf",
    )

    updated = upsert_part_row(
        db,
        partset_id="pub1",
        tag="violin + viola",
        spacing=0.2,
        combined=True,
        file_name="combined.pdf",
        update_on_duplicate=True,
    )
    assert updated.combined is True
    assert updated.spacing == 0.2
    assert updated.file_name == "combined.pdf"


def test_sync_part_rows_from_tags_when_part_already_exists(db: Session) -> None:
    db.add(
        Segment(
            partset_id="pub1",
            page=1,
            top=10.0,
            bottom=50.0,
            tags="viola",
        )
    )
    db.add(
        Part(
            partset_id="pub1",
            tag="viola",
            spacing=0.25,
            combined=False,
            file_name="viola.pdf",
        )
    )
    db.commit()

    sync_part_rows_from_tags(db, "pub1")

    parts = db.query(Part).filter(Part.partset_id == "pub1", Part.tag == "viola").all()
    assert len(parts) == 1
    assert parts[0].spacing == 0.25
