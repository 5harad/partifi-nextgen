from app.score_limits import MAX_SCORE_BYTES, ScoreTooLargeError, score_too_large_message


def test_max_score_bytes() -> None:
    assert MAX_SCORE_BYTES == 250_000_000


def test_score_too_large_message_with_size() -> None:
    assert "188 MB" in score_too_large_message(188_392_869)
    assert "250 MB" in score_too_large_message(188_392_869)


def test_score_too_large_message_generic() -> None:
    assert score_too_large_message() == (
        "This score PDF is too large. The maximum size is 250 MB."
    )


def test_score_too_large_error_uses_message() -> None:
    err = ScoreTooLargeError(61_538_054)
    assert str(err) == score_too_large_message(61_538_054)
