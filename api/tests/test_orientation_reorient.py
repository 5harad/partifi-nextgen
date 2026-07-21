from datetime import datetime
from unittest.mock import MagicMock, patch

from app.models import Part, Partset, Score
from app.services.partset_pages import (
    ensure_page_images_status,
    orientation_data_payload,
    reset_partset_for_reorient,
    start_reorient,
)


def _completed_partset() -> Partset:
    now = datetime.utcnow()
    return Partset(
        id="pub01",
        private_id="priv1",
        title="Test",
        composer="Composer",
        copyright="PD",
        create_ts=now,
        score_id="score01",
        status="analysis",
        import_complete=now,
        convert_complete=now,
        analysis_complete=now,
        convert_progress=100.0,
        analysis_progress=100.0,
        rotation_degrees=90,
        orientation_override="landscape",
    )


def test_reset_partset_for_reorient_clears_completion_flags() -> None:
    partset = _completed_partset()
    db = MagicMock()
    db.query.return_value.filter.return_value.delete.return_value = 0

    with patch("app.services.partset_pages.get_local_cache") as cache_mock:
        reset_partset_for_reorient(db, partset)

    assert partset.status == "convert"
    assert partset.convert_complete is None
    assert partset.analysis_complete is None
    assert partset.convert_progress == 0.0
    assert partset.analysis_progress == 0.0
    assert partset.rotation_degrees == 90
    assert partset.orientation_override == "landscape"
    db.query.assert_any_call(Part)
    cache_mock.return_value.invalidate_partset_pages.assert_called_once_with("pub01")


def test_orientation_data_payload_marks_reimport_in_progress_after_reset() -> None:
    partset = _completed_partset()
    score = Score(id="score01", orientation="portrait")
    db = MagicMock()
    db.query.return_value.filter.return_value.delete.return_value = 0

    with patch("app.services.partset_pages.get_local_cache"):
        reset_partset_for_reorient(db, partset)

    payload = orientation_data_payload(db, partset, score)
    assert payload["reimport_in_progress"] is True
    assert payload["reimport_progress"] < 100.0


def test_orientation_data_accessible_while_reimport_in_progress() -> None:
    partset = _completed_partset()
    db = MagicMock()
    db.query.return_value.filter.return_value.delete.return_value = 0

    with patch("app.services.partset_pages.get_local_cache"):
        reset_partset_for_reorient(db, partset)

    assert partset.import_complete is not None
    assert partset.convert_complete is None
    assert partset.analysis_complete is None


def test_ensure_page_images_status_enqueues_warm_when_rotated_cache_missing() -> None:
    partset = _completed_partset()
    score = Score(id="score01", orientation="portrait")
    db = MagicMock()
    cache = MagicMock()
    cache.partset_has_kind.return_value = False

    with (
        patch("app.services.partset_pages.get_local_cache", return_value=cache),
        patch("app.services.partset_pages.get_partset_cache_error", return_value=None),
        patch("app.services.partset_pages.try_acquire_import_lock", return_value=True) as lock_mock,
        patch("app.services.partset_pages.enqueue_job", return_value="warm-1") as enqueue_mock,
    ):
        status = ensure_page_images_status(db, partset, score)

    assert status["images_ready"] is False
    assert status["images_warming"] is True
    assert status["image_progress"] == 0.0
    lock_mock.assert_called_once_with("pub01")
    enqueue_mock.assert_called_once_with(
        "warm_partset_pages",
        {
            "partset_id": "pub01",
            "score_id": "score01",
            "rotation_degrees": 90,
            "split_two_up": False,
        },
    )
    db.commit.assert_called_once()


def test_ensure_page_images_status_returns_cache_error_without_reenqueue() -> None:
    partset = _completed_partset()
    score = Score(id="score01", orientation="portrait")
    db = MagicMock()
    cache = MagicMock()
    cache.partset_has_kind.return_value = False

    with (
        patch("app.services.partset_pages.get_local_cache", return_value=cache),
        patch(
            "app.services.partset_pages.get_partset_cache_error",
            return_value="cache warm failed",
        ),
        patch("app.services.partset_pages._enqueue_warm_partset_pages") as enqueue_mock,
    ):
        status = ensure_page_images_status(db, partset, score)

    assert status["image_cache_error_message"] == "cache warm failed"
    assert status["images_warming"] is False
    enqueue_mock.assert_not_called()


def test_start_reorient_persists_target_rotation() -> None:
    partset = _completed_partset()
    partset.rotation_degrees = 0
    partset.orientation_override = None
    score = Score(id="score01", orientation="portrait")
    db = MagicMock()
    db.get.return_value = score
    db.query.return_value.filter.return_value.delete.return_value = 0

    with (
        patch("app.services.partset_pages.get_local_cache"),
        patch("app.services.partset_pages.try_acquire_import_lock", return_value=True),
        patch("app.services.partset_pages.enqueue_job", return_value="job-1") as enqueue_mock,
    ):
        job_id = start_reorient(db, partset, 90)

    assert job_id == "job-1"
    assert partset.rotation_degrees == 90
    assert partset.orientation_override == "landscape"
    enqueue_mock.assert_called_once_with(
        "reorient_partset",
        {
            "partset_id": "pub01",
            "score_id": "score01",
            "rotation_degrees": 90,
            "split_two_up": False,
        },
    )
    db.commit.assert_called_once()


def test_start_reorient_split_two_up_requires_landscape_and_persists_layout() -> None:
    partset = _completed_partset()
    partset.rotation_degrees = 0
    score = Score(id="score01", orientation="landscape")
    db = MagicMock()
    db.get.return_value = score
    db.query.return_value.filter.return_value.delete.return_value = 0

    with (
        patch("app.services.partset_pages.get_local_cache"),
        patch("app.services.partset_pages.try_acquire_import_lock", return_value=True),
        patch("app.services.partset_pages.enqueue_job", return_value="job-1") as enqueue_mock,
    ):
        start_reorient(db, partset, 0, split_two_up=True)

    assert partset.split_two_up is True
    assert partset.orientation_override == "portrait"
    enqueue_mock.assert_called_once_with(
        "reorient_partset",
        {
            "partset_id": "pub01",
            "score_id": "score01",
            "rotation_degrees": 0,
            "split_two_up": True,
        },
    )


def test_start_reorient_clears_override_when_rotation_is_zero() -> None:
    partset = _completed_partset()
    partset.orientation_override = "landscape"
    score = Score(id="score01", orientation="portrait")
    db = MagicMock()
    db.get.return_value = score
    db.query.return_value.filter.return_value.delete.return_value = 0

    with (
        patch("app.services.partset_pages.get_local_cache"),
        patch("app.services.partset_pages.try_acquire_import_lock", return_value=True),
        patch("app.services.partset_pages.enqueue_job", return_value="job-0"),
    ):
        start_reorient(db, partset, 0)

    assert partset.rotation_degrees == 0
    assert partset.orientation_override is None


def test_ensure_page_images_status_not_ready_when_only_lowres_cached() -> None:
    partset = _completed_partset()
    score = Score(id="score01", orientation="portrait")
    db = MagicMock()
    cache = MagicMock()
    cache.partset_has_kind.side_effect = lambda _partset_id, kind: kind == "lowres"

    with (
        patch("app.services.partset_pages.get_local_cache", return_value=cache),
        patch("app.services.partset_pages.get_partset_cache_error", return_value=None),
    ):
        status = ensure_page_images_status(db, partset, score)

    assert status["images_ready"] is False
    assert status["images_warming"] is True
