from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import Page, Part, Partset, Score, Segment
from app.services.segments import save_all_page_segments, sync_part_rows_from_tags


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    now = datetime.now(UTC)

    session.add(
        Score(
            id="score1",
            num_pages=2,
            import_complete=now,
            convert_complete=now,
            analysis_complete=now,
        )
    )
    partset = Partset(
        id="pub1",
        private_id="priv1",
        score_id="score1",
        parts_ready=True,
        status="analysis",
        import_complete=now,
        convert_complete=now,
        analysis_complete=now,
    )
    session.add(partset)
    session.add(Page(partset_id="pub1", page=1, left_margin=0, right_margin=100, rotation=0))
    session.add(Page(partset_id="pub1", page=2, left_margin=0, right_margin=100, rotation=0))
    session.commit()
    return session


@patch("app.services.segments.get_local_cache")
def test_save_all_page_segments_syncs_part_rows(mock_cache: Mock, db: Session) -> None:
    mock_cache.return_value = Mock()
    partset = db.get(Partset, "pub1")
    assert partset is not None

    save_all_page_segments(
        db,
        partset,
        {
            "p1": {
                "left_margin": 0,
                "right_margin": 100,
                "rotation": 0,
                "segments": [
                    {
                        "pos": [10.0, 50.0],
                        "tags": "violin",
                        "tag_is_suggestion": False,
                        "label": "",
                        "label_is_suggestion": False,
                    }
                ],
            },
            "p2": {
                "left_margin": 0,
                "right_margin": 100,
                "rotation": 0,
                "segments": [
                    {
                        "pos": [10.0, 50.0],
                        "tags": "cello",
                        "tag_is_suggestion": False,
                        "label": "",
                        "label_is_suggestion": False,
                    }
                ],
            },
        },
    )

    db.expire_all()
    tags = {
        row.tag
        for row in db.query(Part).filter(Part.partset_id == "pub1", Part.combined.is_(False)).all()
    }
    assert tags == {"violin", "cello"}
    assert partset.parts_ready is False


def test_sync_part_rows_from_tags_recovers_when_part_row_races(db: Session) -> None:
    """If another transaction inserts the part row first, sync reuses it instead of 500ing."""
    db.add(
        Segment(
            partset_id="pub1",
            page=1,
            top=10.0,
            bottom=50.0,
            tags="violin II",
        )
    )
    db.flush()

    engine = db.get_bind()
    original_begin_nested = db.begin_nested
    raced = {"done": False}

    def begin_nested_with_race():
        ctx = original_begin_nested()
        if not raced["done"]:
            other = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
            try:
                other.add(
                    Part(
                        partset_id="pub1",
                        tag="violin II",
                        spacing=0.1,
                        combined=False,
                        file_name="violin_II.pdf",
                    )
                )
                other.commit()
            finally:
                other.close()
            raced["done"] = True
        return ctx

    with patch.object(db, "begin_nested", side_effect=begin_nested_with_race):
        sync_part_rows_from_tags(db, "pub1")

    violin_parts = (
        db.query(Part)
        .filter(Part.partset_id == "pub1", Part.tag == "violin II")
        .all()
    )
    assert len(violin_parts) == 1
