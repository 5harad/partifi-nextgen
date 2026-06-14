from jobs.errors import MAX_ERROR_MESSAGE_LEN, truncate_error_message


def test_truncate_error_message_none() -> None:
    assert truncate_error_message(None) is None


def test_truncate_error_message_normalizes_whitespace() -> None:
    assert truncate_error_message("foo\n\nbar") == "foo bar"


def test_truncate_error_message_long() -> None:
    msg = "x" * (MAX_ERROR_MESSAGE_LEN + 10)
    truncated = truncate_error_message(msg)
    assert truncated is not None
    assert len(truncated) == MAX_ERROR_MESSAGE_LEN
    assert truncated.endswith("...")
