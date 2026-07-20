from unittest.mock import patch

from jobs.clean_cache import _invalidate_completed_parts


def test_invalidate_completed_parts_clears_stale_generation_progress() -> None:
    with patch("jobs.clean_cache.db_conn.execute") as execute:
        _invalidate_completed_parts("partset-1")

    query, params = execute.call_args.args
    assert "status = 'analysis'" in query
    assert "parts_ready = 0" in query
    assert "cut_progress = 0" in query
    assert "paste_progress = 0" in query
    assert "WHERE id = :id AND parts_ready = 1" in query
    assert params == {"id": "partset-1"}
