from unittest.mock import MagicMock, patch

from jobs.errors import mark_partset_error


@patch("jobs.errors.db_conn.execute")
@patch("jobs.errors.db_conn.fetchone")
def test_mark_partset_error_when_parts_ready_is_null(
    mock_fetchone: MagicMock,
    mock_execute: MagicMock,
) -> None:
    mock_fetchone.return_value = MagicMock(status="import", parts_ready=None)

    mark_partset_error("B3yzC", "import", message="No downloadable PDF")

    mock_execute.assert_called_once()
    query = mock_execute.call_args[0][0]
    assert "parts_ready IS NULL OR parts_ready = 0" in query


@patch("jobs.errors.db_conn.execute")
@patch("jobs.errors.db_conn.fetchone")
def test_mark_partset_error_skips_when_parts_ready(
    mock_fetchone: MagicMock,
    mock_execute: MagicMock,
) -> None:
    mock_fetchone.return_value = MagicMock(status="analysis", parts_ready=1)

    mark_partset_error("pub01", "import", message="late failure")

    mock_execute.assert_not_called()
