from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import Part, Partset, Score
from app.services.preview import start_part_generation


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
    _mock_sync: Mock,
    _mock_lock: Mock,
    mock_enqueue: Mock,
    db: Session,
) -> None:
    partset = db.get(Partset, "pub1")
    assert partset is not None

    job_id = start_part_generation(db, partset)

    assert job_id is None
    mock_enqueue.assert_not_called()
