from datetime import datetime
from unittest.mock import MagicMock, patch

from app.models import Partset, Score
from app.services.partset_pages import (
    ensure_page_images_status,
    orientation_data_payload,
    reset_partset_for_reorient,
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
    assert partset.rotation_degrees == 0
    assert partset.orientation_override is None
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
        },
    )
    db.commit.assert_called_once()
