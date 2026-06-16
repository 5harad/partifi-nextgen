from unittest.mock import MagicMock, patch

from app.services.score_pages import ensure_score_pages_warming, score_pages_available


def _score_db(*, s3: bool = True, file_size: int = 1024) -> MagicMock:
    score = MagicMock()
    score.s3 = s3
    score.file_size = file_size
    db = MagicMock()
    db.get.return_value = score
    return db


@patch("app.services.score_pages.get_local_cache")
def test_score_pages_available_local(mock_cache_fn: patch) -> None:
    cache = MagicMock()
    cache.score_has_pages.return_value = True
    mock_cache_fn.return_value = cache
    assert score_pages_available("abc12") is True


@patch("app.services.score_pages.get_local_cache")
def test_score_pages_available_missing(mock_cache_fn: patch) -> None:
    cache = MagicMock()
    cache.score_has_pages.return_value = False
    mock_cache_fn.return_value = cache
    assert score_pages_available("abc12") is False


@patch("app.services.score_pages.get_warm_progress", return_value=0.0)
@patch("app.services.score_pages.enqueue_job", return_value="7")
@patch("app.services.score_pages.try_acquire_score_pages_lock", return_value=True)
@patch("app.services.score_pages.get_local_cache")
def test_ensure_score_pages_warming_enqueues(
    mock_cache_fn: patch,
    _mock_lock: patch,
    mock_enqueue: patch,
    _mock_progress: patch,
) -> None:
    cache = MagicMock()
    cache.score_has_pages.return_value = False
    mock_cache_fn.return_value = cache

    status = ensure_score_pages_warming(_score_db(), "abc12")

    assert status["images_ready"] is False
    assert status["images_warming"] is True
    assert status["image_progress"] == 0.0
    mock_enqueue.assert_called_once_with("warm_score_pages", {"score_id": "abc12"})


@patch("app.services.score_pages.get_warm_progress", return_value=42.5)
@patch("app.services.score_pages.enqueue_job")
@patch("app.services.score_pages.try_acquire_score_pages_lock", return_value=False)
@patch("app.services.score_pages.get_local_cache")
def test_ensure_score_pages_warming_skips_enqueue_when_locked(
    mock_cache_fn: patch,
    _mock_lock: patch,
    mock_enqueue: patch,
    _mock_progress: patch,
) -> None:
    cache = MagicMock()
    cache.score_has_pages.return_value = False
    mock_cache_fn.return_value = cache

    status = ensure_score_pages_warming(_score_db(), "abc12")

    assert status == {"images_ready": False, "images_warming": True, "image_progress": 42.5}
    mock_enqueue.assert_not_called()


@patch("app.services.score_pages.release_score_pages_lock")
@patch("app.services.score_pages.reset_warm_progress")
@patch("app.services.score_pages.get_warm_progress", return_value=100.0)
@patch("app.services.score_pages.enqueue_job", return_value="9")
@patch("app.services.score_pages.try_acquire_score_pages_lock", return_value=True)
@patch("app.services.score_pages.get_local_cache")
def test_ensure_score_pages_warming_retries_when_progress_stuck_at_100(
    mock_cache_fn: patch,
    _mock_lock: patch,
    mock_enqueue: patch,
    _mock_progress: patch,
    mock_reset: patch,
    mock_release: patch,
) -> None:
    cache = MagicMock()
    cache.score_has_pages.return_value = False
    mock_cache_fn.return_value = cache

    status = ensure_score_pages_warming(_score_db(), "abc12")

    assert status == {"images_ready": False, "images_warming": True, "image_progress": 0.0}
    mock_release.assert_called_once_with("abc12")
    mock_reset.assert_called_once_with("abc12")
    mock_enqueue.assert_called_once_with("warm_score_pages", {"score_id": "abc12"})


@patch("app.services.score_pages.enqueue_job")
@patch("app.services.score_pages.try_acquire_score_pages_lock")
@patch("app.services.score_pages.get_local_cache")
def test_ensure_score_pages_ready_when_cached(
    mock_cache_fn: patch,
    _mock_lock: patch,
    mock_enqueue: patch,
) -> None:
    cache = MagicMock()
    cache.score_has_pages.return_value = True
    mock_cache_fn.return_value = cache

    status = ensure_score_pages_warming(_score_db(), "abc12")

    assert status == {"images_ready": True, "images_warming": False, "image_progress": 100.0}
    mock_enqueue.assert_not_called()
    _mock_lock.assert_not_called()


@patch("app.services.score_pages.enqueue_job")
@patch("app.services.score_pages.get_local_cache")
def test_ensure_score_pages_warming_skips_when_score_unavailable(
    mock_cache_fn: patch,
    mock_enqueue: patch,
) -> None:
    cache = MagicMock()
    cache.score_has_pages.return_value = False
    mock_cache_fn.return_value = cache
    db = MagicMock()
    db.get.return_value = None

    status = ensure_score_pages_warming(db, "abc12")

    assert status == {"images_ready": False, "images_warming": False, "image_progress": 0.0}
    mock_enqueue.assert_not_called()
