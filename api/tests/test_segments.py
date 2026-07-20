from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import Page, Part, Partset, Score, Segment
from app.services.segments import (
    _retry_segment_save_on_deadlock,
    save_all_page_segments,
    sync_part_rows_from_tags,
)


class MySqlError(Exception):
    pass


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


@patch("app.services.segments.get_local_cache")
def test_save_all_page_segments_updates_dirty_subset_atomically(mock_cache: Mock, db: Session) -> None:
    mock_cache.return_value = Mock()
    partset = db.get(Partset, "pub1")
    assert partset is not None
    db.add(
        Segment(
            partset_id="pub1",
            page=2,
            top=10,
            bottom=50,
            tags="cello",
        )
    )
    db.commit()

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
            }
        },
    )

    db.expire_all()
    page_two_segments = db.query(Segment).filter(Segment.partset_id == "pub1", Segment.page == 2).all()
    assert [segment.tags for segment in page_two_segments] == ["cello"]
    tags = {
        row.tag
        for row in db.query(Part).filter(Part.partset_id == "pub1", Part.combined.is_(False)).all()
    }
    assert tags == {"violin", "cello"}
    mock_cache.return_value.invalidate_preview.assert_called_once_with("pub1")
    mock_cache.return_value.invalidate_parts.assert_called_once_with("pub1")


def test_save_all_page_segments_rejects_noncanonical_page_keys(db: Session) -> None:
    partset = db.get(Partset, "pub1")
    assert partset is not None

    with pytest.raises(ValueError, match="Invalid page key: p01"):
        save_all_page_segments(db, partset, {"p1": {}, "p01": {}})


@patch("app.services.segments.get_local_cache")
def test_save_page_segments_collapses_plus_in_tag(mock_cache: Mock, db: Session) -> None:
    # "+" is the reserved combined-part delimiter. A user-typed tag like
    # "git + rhyth" must collapse to a single tag so it yields one real part
    # rather than being split and deleted during sync (regression: 0 parts).
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
                        "tags": "git + rhyth",
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
                "segments": [],
            },
        },
    )

    db.expire_all()
    stored = {row.tags for row in db.query(Segment).filter(Segment.partset_id == "pub1").all()}
    assert stored == {"git rhyth"}
    tags = {
        row.tag
        for row in db.query(Part).filter(Part.partset_id == "pub1", Part.combined.is_(False)).all()
    }
    assert tags == {"git rhyth"}


@patch("app.services.segments.get_local_cache")
def test_sync_part_rows_from_tags_is_idempotent(mock_cache: Mock, db: Session) -> None:
    mock_cache.return_value = Mock()
    db.add(
        Segment(
            partset_id="pub1",
            page=1,
            top=10.0,
            bottom=50.0,
            tags="violin II",
        )
    )
    db.commit()

    sync_part_rows_from_tags(db, "pub1")
    sync_part_rows_from_tags(db, "pub1")

    assert (
        db.query(Part)
        .filter(Part.partset_id == "pub1", Part.tag == "violin II")
        .count()
        == 1
    )


def test_segment_save_retries_mysql_deadlock(db: Session) -> None:
    deadlock = OperationalError(
        statement=None,
        params=None,
        orig=MySqlError(1213, "Deadlock found when trying to get lock"),
    )
    save = Mock(side_effect=[deadlock, None])

    with (
        patch.object(db, "rollback", wraps=db.rollback) as rollback,
        patch("app.services.segments.time.sleep") as sleep,
    ):
        _retry_segment_save_on_deadlock(db, "pub1", save)

    assert save.call_count == 2
    rollback.assert_called_once()
    sleep.assert_called_once()


def test_segment_save_rolls_back_final_mysql_deadlock(db: Session) -> None:
    deadlock = OperationalError(
        statement=None,
        params=None,
        orig=MySqlError(1213, "Deadlock found when trying to get lock"),
    )
    save = Mock(side_effect=deadlock)

    with (
        patch.object(db, "rollback", wraps=db.rollback) as rollback,
        patch("app.services.segments.time.sleep") as sleep,
        pytest.raises(OperationalError, match="Deadlock found"),
    ):
        _retry_segment_save_on_deadlock(db, "pub1", save)

    assert save.call_count == 3
    assert rollback.call_count == 3
    assert sleep.call_count == 2


def test_segment_save_does_not_retry_other_database_errors(db: Session) -> None:
    lock_wait_timeout = OperationalError(
        statement=None,
        params=None,
        orig=MySqlError(1205, "Lock wait timeout exceeded"),
    )
    save = Mock(side_effect=lock_wait_timeout)

    with (
        patch.object(db, "rollback", wraps=db.rollback) as rollback,
        patch("app.services.segments.time.sleep") as sleep,
        pytest.raises(OperationalError, match="Lock wait timeout"),
    ):
        _retry_segment_save_on_deadlock(db, "pub1", save)

    save.assert_called_once()
    rollback.assert_not_called()
    sleep.assert_not_called()
