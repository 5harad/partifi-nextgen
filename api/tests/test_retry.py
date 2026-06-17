from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from app.models import Partset
from app.services.retry import (
    ensure_import_if_needed,
    import_pipeline_complete,
    retry_partset_pipeline,
)


def _partset(**kwargs) -> Partset:
    defaults = {
        "id": "pub01",
        "private_id": "priv01",
        "score_id": "score1",
        "imslp_id": None,
        "import_complete": None,
        "convert_complete": None,
        "analysis_complete": None,
        "parts_ready": False,
        "error": "convert",
    }
    defaults.update(kwargs)
    return Partset(**defaults)


def test_import_pipeline_complete() -> None:
    incomplete = _partset(import_complete=datetime.utcnow())
    assert not import_pipeline_complete(incomplete)

    complete = _partset(
        import_complete=datetime.utcnow(),
        convert_complete=datetime.utcnow(),
        analysis_complete=datetime.utcnow(),
    )
    assert import_pipeline_complete(complete)


@patch("app.services.retry.try_acquire_import_lock", return_value=True)
@patch("app.services.retry.enqueue_job", return_value="55")
def test_ensure_import_imslp_orphan(_mock_enqueue: patch, _mock_lock: patch) -> None:
    db = Mock()
    partset = _partset(
        score_id=None,
        imslp_id="268573",
        error=None,
        import_start=None,
        status=None,
    )
    job_id = ensure_import_if_needed(db, partset)
    assert job_id == "55"
    assert partset.import_start is not None
    assert partset.status == "import"
    assert partset.error is None
    _mock_enqueue.assert_called_once_with(
        "imslp_import",
        {"partset_id": "pub01", "imslp_id": "268573"},
    )
    db.commit.assert_called_once()


@patch("app.services.retry.enqueue_job")
def test_ensure_import_skips_when_complete(_mock_enqueue: patch) -> None:
    db = Mock()
    now = datetime.utcnow()
    partset = _partset(
        import_complete=now,
        convert_complete=now,
        analysis_complete=now,
        error=None,
    )
    assert ensure_import_if_needed(db, partset) is None
    _mock_enqueue.assert_not_called()
    db.commit.assert_not_called()


@patch("app.services.retry.enqueue_job")
def test_ensure_import_skips_when_error_set(_mock_enqueue: patch) -> None:
    db = Mock()
    partset = _partset(score_id=None, imslp_id="268573", error="import")
    assert ensure_import_if_needed(db, partset) is None
    _mock_enqueue.assert_not_called()


@patch("app.services.retry.try_acquire_import_lock", return_value=False)
@patch("app.services.retry.enqueue_job")
def test_ensure_import_skips_when_lock_held(_mock_enqueue: patch, _mock_lock: patch) -> None:
    db = Mock()
    partset = _partset(score_id=None, imslp_id="268573", error=None)
    assert ensure_import_if_needed(db, partset) is None
    _mock_enqueue.assert_not_called()
    db.commit.assert_not_called()


@patch("app.services.retry.try_acquire_import_lock", return_value=True)
@patch("app.services.retry.enqueue_job", return_value="42")
def test_retry_import_pipeline(_mock_enqueue: patch, _mock_lock: patch) -> None:
    db = Mock()
    partset = _partset(error="analysis")
    stage, job_id = retry_partset_pipeline(db, partset)
    assert stage == "import"
    assert job_id == "42"
    assert partset.error is None
    _mock_enqueue.assert_called_once_with(
        "import_pipeline",
        {"partset_id": "pub01", "score_id": "score1"},
    )
    db.commit.assert_called_once()


@patch("app.services.retry.try_acquire_import_lock", return_value=True)
@patch("app.services.retry.enqueue_job", return_value="99")
def test_retry_imslp_import(_mock_enqueue: patch, _mock_lock: patch) -> None:
    db = Mock()
    partset = _partset(score_id=None, imslp_id="IMSLP123", error="import")
    stage, job_id = retry_partset_pipeline(db, partset)
    assert stage == "import"
    assert job_id == "99"
    _mock_enqueue.assert_called_once_with(
        "imslp_import",
        {"partset_id": "pub01", "imslp_id": "IMSLP123"},
    )


@patch("app.services.retry.try_acquire_import_lock", return_value=False)
@patch("app.services.retry.enqueue_job")
def test_retry_import_skips_when_lock_held(_mock_enqueue: patch, _mock_lock: patch) -> None:
    db = Mock()
    partset = _partset(score_id=None, imslp_id="IMSLP123", error="import")
    stage, job_id = retry_partset_pipeline(db, partset)
    assert stage == "import"
    assert job_id is None
    _mock_enqueue.assert_not_called()


@patch("app.services.retry.try_acquire_gen_parts_lock", return_value=True)
@patch("app.services.retry.enqueue_job", return_value="7")
def test_retry_partgen(_mock_enqueue: patch, _mock_lock: patch) -> None:
    db = Mock()
    now = datetime.utcnow()
    partset = _partset(
        import_complete=now,
        convert_complete=now,
        analysis_complete=now,
        error="cut",
    )
    stage, job_id = retry_partset_pipeline(db, partset)
    assert stage == "partgen"
    assert job_id == "7"
    _mock_enqueue.assert_called_once_with("gen_parts", {"partset_id": "pub01"})


def test_retry_nothing_left() -> None:
    db = Mock()
    now = datetime.utcnow()
    partset = _partset(
        import_complete=now,
        convert_complete=now,
        analysis_complete=now,
        parts_ready=True,
        error=None,
    )
    with pytest.raises(ValueError, match="Nothing to retry"):
        retry_partset_pipeline(db, partset)
