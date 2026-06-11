from unittest.mock import MagicMock, patch

from app.services.score_pages import ensure_score_pages_warming, score_pages_available


@patch("app.services.score_pages.score_page_images_on_s3", return_value=False)
@patch("app.services.score_pages.get_local_cache")
def test_score_pages_available_local(mock_cache_fn: patch, _mock_s3: patch) -> None:
    cache = MagicMock()
    cache.score_has_pages.return_value = True
    mock_cache_fn.return_value = cache
    assert score_pages_available("abc12") is True
    _mock_s3.assert_not_called()


@patch("app.services.score_pages.score_page_images_on_s3", return_value=True)
@patch("app.services.score_pages.get_local_cache")
def test_score_pages_available_s3(mock_cache_fn: patch, _mock_s3: patch) -> None:
    cache = MagicMock()
    cache.score_has_pages.return_value = False
    mock_cache_fn.return_value = cache
    assert score_pages_available("abc12") is True


@patch("app.services.score_pages.enqueue_job", return_value="7")
@patch("app.services.score_pages.try_acquire_score_pages_lock", return_value=True)
@patch("app.services.score_pages.score_page_images_on_s3", return_value=False)
@patch("app.services.score_pages.get_local_cache")
def test_ensure_score_pages_warming_enqueues(
    mock_cache_fn: patch,
    _mock_s3: patch,
    _mock_lock: patch,
    mock_enqueue: patch,
) -> None:
    cache = MagicMock()
    cache.score_has_pages.return_value = False
    mock_cache_fn.return_value = cache

    status = ensure_score_pages_warming("abc12")

    assert status == {"images_ready": False, "images_warming": True}
    mock_enqueue.assert_called_once_with("warm_score_pages", {"score_id": "abc12"})


@patch("app.services.score_pages.enqueue_job")
@patch("app.services.score_pages.try_acquire_score_pages_lock", return_value=False)
@patch("app.services.score_pages.score_page_images_on_s3", return_value=False)
@patch("app.services.score_pages.get_local_cache")
def test_ensure_score_pages_warming_skips_enqueue_when_locked(
    mock_cache_fn: patch,
    _mock_s3: patch,
    _mock_lock: patch,
    mock_enqueue: patch,
) -> None:
    cache = MagicMock()
    cache.score_has_pages.return_value = False
    mock_cache_fn.return_value = cache

    status = ensure_score_pages_warming("abc12")

    assert status == {"images_ready": False, "images_warming": True}
    mock_enqueue.assert_not_called()


@patch("app.services.score_pages.enqueue_job")
@patch("app.services.score_pages.try_acquire_score_pages_lock")
@patch("app.services.score_pages.score_page_images_on_s3", return_value=True)
@patch("app.services.score_pages.get_local_cache")
def test_ensure_score_pages_ready_when_cached(
    mock_cache_fn: patch,
    _mock_s3: patch,
    _mock_lock: patch,
    mock_enqueue: patch,
) -> None:
    cache = MagicMock()
    cache.score_has_pages.return_value = True
    mock_cache_fn.return_value = cache

    status = ensure_score_pages_warming("abc12")

    assert status == {"images_ready": True, "images_warming": False}
    mock_enqueue.assert_not_called()
    _mock_lock.assert_not_called()
