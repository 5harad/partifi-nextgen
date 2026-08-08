from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import Partset, Score
from app.services.partset_admin import update_partset_metadata


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
            title="Old title",
            composer="Old composer",
            copyright="unknown",
            parts_ready=True,
            status="paste",
            cut_start=now,
            cut_complete=now,
            cut_progress=100,
            paste_start=now,
            paste_complete=now,
            paste_progress=100,
            import_complete=now,
            convert_complete=now,
            analysis_complete=now,
        )
    )
    session.commit()
    return session


@patch("app.services.preview.gen_parts_lock_held", return_value=False)
@patch("app.services.partset_admin.get_local_cache")
def test_update_partset_metadata_invalidates_parts(
    mock_get_cache: Mock,
    _mock_lock_held: Mock,
    db: Session,
) -> None:
    mock_cache = Mock()
    mock_get_cache.return_value = mock_cache
    partset = db.get(Partset, "pub1")
    assert partset is not None

    update_partset_metadata(
        db,
        partset,
        title="梁祝",
        composer="何占豪",
        publisher="",
        copyright="before 1923",
    )

    db.expire_all()
    updated = db.get(Partset, "pub1")
    assert updated is not None
    assert updated.title == "梁祝"
    assert updated.composer == "何占豪"
    assert updated.copyright == "before 1923"
    assert updated.parts_ready is False
    assert updated.status == "analysis"
    assert updated.cut_start is None
    assert updated.cut_complete is None
    assert updated.cut_progress == 0
    assert updated.paste_start is None
    assert updated.paste_complete is None
    assert updated.paste_progress == 0
    mock_cache.invalidate_parts.assert_called_once_with("pub1")


@patch("app.services.preview.gen_parts_lock_held", return_value=False)
@patch("app.services.partset_admin.get_local_cache")
def test_update_partset_metadata_preserves_active_generation_progress(
    mock_get_cache: Mock,
    _mock_lock_held: Mock,
    db: Session,
) -> None:
    mock_get_cache.return_value = Mock()
    partset = db.get(Partset, "pub1")
    assert partset is not None
    now = datetime.now(UTC)
    partset.parts_ready = False
    partset.status = "paste"
    partset.paste_start = now
    partset.paste_complete = None
    partset.paste_progress = 50
    db.commit()

    update_partset_metadata(
        db,
        partset,
        title="Updated title",
        composer="Updated composer",
        publisher="Publisher",
        copyright="unknown",
    )

    db.expire_all()
    updated = db.get(Partset, "pub1")
    assert updated is not None
    assert updated.status == "paste"
    assert updated.paste_start is not None
    assert updated.paste_complete is None
    assert updated.paste_progress == 50


@patch("app.services.preview.gen_parts_lock_held", return_value=False)
@patch("app.services.partset_admin.get_local_cache")
def test_update_partset_metadata_clears_stale_invalidated_generation_progress(
    mock_get_cache: Mock,
    _mock_lock_held: Mock,
    db: Session,
) -> None:
    mock_get_cache.return_value = Mock()
    partset = db.get(Partset, "pub1")
    assert partset is not None
    now = datetime.now(UTC)
    partset.parts_ready = False
    partset.status = "paste"
    partset.paste_start = now
    partset.paste_complete = now
    partset.paste_progress = 100
    db.commit()

    update_partset_metadata(
        db,
        partset,
        title="Updated title",
        composer="Updated composer",
        publisher="Publisher",
        copyright="unknown",
    )

    db.expire_all()
    updated = db.get(Partset, "pub1")
    assert updated is not None
    assert updated.status == "analysis"
    assert updated.cut_start is None
    assert updated.cut_complete is None
    assert updated.cut_progress == 0
    assert updated.paste_start is None
    assert updated.paste_complete is None
    assert updated.paste_progress == 0


@patch("app.services.preview.gen_parts_lock_held", return_value=False)
@patch("app.services.partset_admin.get_local_cache")
def test_update_partset_metadata_copyright_only_keeps_parts(
    mock_get_cache: Mock,
    _mock_lock_held: Mock,
    db: Session,
) -> None:
    mock_cache = Mock()
    mock_get_cache.return_value = mock_cache
    partset = db.get(Partset, "pub1")
    assert partset is not None

    update_partset_metadata(
        db,
        partset,
        title="Old title",
        composer="Old composer",
        publisher="",
        copyright="after 1923",
    )

    db.expire_all()
    updated = db.get(Partset, "pub1")
    assert updated is not None
    assert updated.copyright == "after 1923"
    assert updated.parts_ready is True
    assert updated.status == "paste"
    mock_cache.invalidate_parts.assert_not_called()


@patch("app.services.preview.gen_parts_lock_held", return_value=False)
@patch("app.services.partset_admin.get_local_cache")
def test_update_partset_metadata_publisher_only_keeps_parts(
    mock_get_cache: Mock,
    _mock_lock_held: Mock,
    db: Session,
) -> None:
    mock_cache = Mock()
    mock_get_cache.return_value = mock_cache
    partset = db.get(Partset, "pub1")
    assert partset is not None
    partset.publisher = ""
    db.commit()

    update_partset_metadata(
        db,
        partset,
        title="Old title",
        composer="Old composer",
        publisher="Breitkopf",
        copyright="unknown",
    )

    db.expire_all()
    updated = db.get(Partset, "pub1")
    assert updated is not None
    assert updated.publisher == "Breitkopf"
    assert updated.parts_ready is True
    assert updated.status == "paste"
    mock_cache.invalidate_parts.assert_not_called()
