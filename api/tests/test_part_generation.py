from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import Part, Partset, Score
from app.services.preview import ensure_part_file_on_cache_miss, start_part_generation


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    now = datetime.now(UTC)

    session.add(Score(id="score1", num_pages=1, import_complete=now, analysis_complete=now))
    session.add(
        Partset(
            id="pub1",
            private_id="priv1",
            score_id="score1",
            parts_ready=False,
            status="cut",
            error="cut",
            error_message="HeadObject 404",
            import_complete=now,
            convert_complete=now,
            analysis_complete=now,
        )
    )
    session.add(
        Part(
            partset_id="pub1",
            tag="violin",
            spacing=0.1,
            combined=False,
            file_name="violin.pdf",
        )
    )
    session.commit()
    return session


@patch("app.services.preview.enqueue_job", return_value="job-99")
@patch("app.services.preview.try_acquire_gen_parts_lock", return_value=True)
@patch("app.services.preview.clear_partset_failure")
@patch("app.services.preview.sync_part_rows_from_tags")
def test_start_part_generation_retries_when_stuck_in_cut(
    _mock_sync: Mock,
    mock_clear: Mock,
    _mock_lock: Mock,
    mock_enqueue: Mock,
    db: Session,
) -> None:
    partset = db.get(Partset, "pub1")
    assert partset is not None

    job_id = start_part_generation(db, partset)

    assert job_id == "job-99"
    mock_clear.assert_called_once_with(partset)
    mock_enqueue.assert_called_once_with("gen_parts", {"partset_id": "pub1"})


@patch("app.services.preview.enqueue_job")
@patch("app.services.preview.try_acquire_gen_parts_lock", return_value=False)
@patch("app.services.preview.sync_part_rows_from_tags")
def test_start_part_generation_skips_when_lock_held(
    mock_sync: Mock,
    _mock_lock: Mock,
    mock_enqueue: Mock,
    db: Session,
) -> None:
    partset = db.get(Partset, "pub1")
    assert partset is not None

    job_id = start_part_generation(db, partset)

    assert job_id is None
    mock_sync.assert_not_called()
    mock_enqueue.assert_not_called()


@patch("app.services.preview.enqueue_job")
@patch("app.services.preview.try_acquire_gen_parts_lock")
@patch("app.services.preview.sync_part_rows_from_tags")
def test_start_part_generation_skips_when_paste_in_progress(
    mock_sync: Mock,
    mock_lock: Mock,
    mock_enqueue: Mock,
    db: Session,
) -> None:
    partset = db.get(Partset, "pub1")
    assert partset is not None
    partset.error = None
    partset.paste_start = datetime.now(UTC)
    partset.paste_complete = None

    job_id = start_part_generation(db, partset)

    assert job_id is None
    mock_lock.assert_not_called()
    mock_sync.assert_not_called()
    mock_enqueue.assert_not_called()


@patch("app.services.preview.ensure_parts_if_needed", return_value="job-1")
@patch("app.services.preview.get_local_cache")
def test_ensure_part_file_on_cache_miss_clears_parts_ready(
    mock_get_cache: Mock,
    mock_ensure: Mock,
    db: Session,
) -> None:
    mock_get_cache.return_value.part_is_cached.return_value = False
    partset = db.get(Partset, "pub1")
    assert partset is not None
    partset.parts_ready = True
    db.commit()

    ensure_part_file_on_cache_miss(db, partset, "pub1_violin.pdf")

    assert partset.parts_ready is False
    mock_ensure.assert_called_once()


@patch("app.services.preview.ensure_parts_if_needed", return_value=None)
@patch("app.services.preview.get_local_cache")
def test_ensure_part_file_on_cache_miss_persists_when_not_enqueued(
    mock_get_cache: Mock,
    mock_ensure: Mock,
    db: Session,
) -> None:
    mock_get_cache.return_value.part_is_cached.return_value = False
    partset = db.get(Partset, "pub1")
    assert partset is not None
    partset.parts_ready = True
    db.commit()

    ensure_part_file_on_cache_miss(db, partset, "pub1_violin.pdf")

    db.refresh(partset)
    assert partset.parts_ready is False


@patch("app.services.preview.ensure_parts_if_needed")
@patch("app.services.preview.get_local_cache")
def test_ensure_part_file_on_cache_miss_skips_when_cached(
    mock_get_cache: Mock,
    mock_ensure: Mock,
    db: Session,
) -> None:
    mock_get_cache.return_value.part_is_cached.return_value = True
    partset = db.get(Partset, "pub1")
    assert partset is not None

    ensure_part_file_on_cache_miss(db, partset, "pub1_violin.pdf")

    mock_ensure.assert_not_called()
