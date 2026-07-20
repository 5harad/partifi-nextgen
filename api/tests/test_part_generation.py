from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import Part, Partset, Score
from app.routers.v1 import ensure_parts, generate_parts
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
def test_start_part_generation_enqueues_when_no_error(
    _mock_sync: Mock,
    mock_clear: Mock,
    _mock_lock: Mock,
    mock_enqueue: Mock,
    db: Session,
) -> None:
    partset = db.get(Partset, "pub1")
    assert partset is not None
    partset.error = None
    partset.error_message = None

    job_id = start_part_generation(db, partset)

    assert job_id == "job-99"
    mock_clear.assert_called_once_with(partset)
    mock_enqueue.assert_called_once_with("gen_parts", {"partset_id": "pub1"})


@patch("app.services.preview.enqueue_job")
@patch("app.services.preview.try_acquire_gen_parts_lock", return_value=True)
@patch("app.services.preview.clear_partset_failure")
@patch("app.services.preview.sync_part_rows_from_tags")
def test_start_part_generation_skips_when_error_set(
    _mock_sync: Mock,
    mock_clear: Mock,
    _mock_lock: Mock,
    mock_enqueue: Mock,
    db: Session,
) -> None:
    partset = db.get(Partset, "pub1")
    assert partset is not None

    job_id = start_part_generation(db, partset)

    assert job_id is None
    mock_clear.assert_not_called()
    mock_enqueue.assert_not_called()


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


@patch("app.routers.v1.verify_csrf")
@patch("app.routers.v1.start_part_generation", return_value=None)
@patch("app.routers.v1.get_partset_by_private_id")
def test_generate_parts_reports_when_parts_are_already_ready(
    mock_partset: Mock,
    _mock_start: Mock,
    _mock_csrf: Mock,
) -> None:
    mock_partset.return_value = SimpleNamespace(parts_ready=True)

    response = generate_parts("priv1", "csrf", db=Mock())

    assert response.job_id is None
    assert response.parts_ready is True


@patch("app.routers.v1.start_part_generation", side_effect=ValueError("No parts tagged for generation"))
@patch("app.routers.v1.resolve_partset_access")
def test_ensure_parts_reports_generation_start_errors(
    mock_resolve: Mock,
    _mock_start: Mock,
) -> None:
    mock_resolve.return_value = (Mock(), "owner")

    with pytest.raises(HTTPException, match="No parts tagged for generation") as exc_info:
        ensure_parts("access1", db=Mock())

    assert exc_info.value.status_code == 400
