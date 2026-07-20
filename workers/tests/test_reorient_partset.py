from unittest.mock import MagicMock, patch

from jobs import reorient_partset


@patch("jobs.reorient_partset.db_conn.execute")
def test_reset_partset_for_reorient_deletes_stale_parts(mock_execute: MagicMock) -> None:
    reorient_partset._reset_partset_for_reorient("partset-1")

    queries = [call.args[0] for call in mock_execute.call_args_list]
    assert "DELETE FROM parts WHERE partset_id = :partset_id" in queries
