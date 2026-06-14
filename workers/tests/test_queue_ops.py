import time
from unittest.mock import patch

from queue_ops import _is_stale, reap_stale_jobs


def test_is_stale_uses_started_at() -> None:
    job = {"started_at": int(time.time()) - 100}
    assert not _is_stale(job, stale_after_seconds=200)
    assert _is_stale(job, stale_after_seconds=50)


def test_is_stale_falls_back_to_enqueued_at() -> None:
    job = {"enqueued_at": int(time.time()) - 500}
    assert _is_stale(job, stale_after_seconds=100)


def test_is_stale_without_timestamps() -> None:
    assert _is_stale({}, stale_after_seconds=100)


@patch("queue_ops.mark_partset_error")
@patch("queue_ops.get_settings")
def test_reap_stale_jobs_marks_failed(mock_settings, mock_mark_error) -> None:
    mock_settings.return_value.job_timeout_seconds = 60
    stale_job = {
        "id": "9",
        "type": "gen_parts",
        "payload": {"partset_id": "abc12"},
        "started_at": int(time.time()) - 1000,
    }
    raw = __import__("json").dumps(stale_job)

    class FakeRedis:
        def lrange(self, _key, _start, _end):
            return [raw]

        def lrem(self, _key, _count, value):
            assert value == raw
            return 1

    assert reap_stale_jobs(FakeRedis()) == 1
    mock_mark_error.assert_called_once()
    args, kwargs = mock_mark_error.call_args
    assert args[0] == "abc12"
    assert kwargs["message"] == "Job lost in processing queue (worker likely crashed)"
    assert kwargs["job_id"] == "9"
