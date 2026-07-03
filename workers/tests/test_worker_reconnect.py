from worker import should_reconnect_after_redis_error


def test_reconnect_when_running_sleeps_and_returns_true() -> None:
    slept: list[float] = []
    result = should_reconnect_after_redis_error(
        running=True,
        backoff_seconds=2.0,
        sleep=slept.append,
    )
    assert result is True
    assert slept == [2.0]


def test_no_reconnect_during_shutdown() -> None:
    slept: list[float] = []
    result = should_reconnect_after_redis_error(
        running=False,
        backoff_seconds=2.0,
        sleep=slept.append,
    )
    assert result is False
    assert slept == []
