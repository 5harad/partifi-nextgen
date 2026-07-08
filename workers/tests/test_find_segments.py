from unittest.mock import patch

from find_segments import _cap_segments, analyze_score


def test_cap_segments_sorts_sampled_cuts() -> None:
    segments = list(range(100))
    # Distinct unordered sample so sorted order is the only valid result.
    unordered = [90, 10, 50, 20, 80, 5, 70, 15, 60, 25] + list(range(30, 50))
    assert len(unordered) == 30
    assert len(set(unordered)) == 30
    with patch("find_segments.random.sample", return_value=unordered):
        capped = _cap_segments(segments, 30)
    assert capped == sorted(unordered)
    assert all(capped[i] < capped[i + 1] for i in range(len(capped) - 1))


def test_cap_segments_noop_when_under_limit() -> None:
    segments = [10, 20, 30]
    assert _cap_segments(segments, 30) is segments


def test_analyze_score_clears_partial_rows_before_rewrite() -> None:
    calls: list[tuple[str, dict]] = []

    def fake_execute(sql: str, params: dict | None = None) -> None:
        calls.append((sql, params or {}))

    with (
        patch("find_segments.db_conn.execute", side_effect=fake_execute),
        patch("find_segments.par_find_segments") as par,
    ):
        analyze_score("part01", ["/tmp/page-1.png"])

    delete_sqls = [sql for sql, _ in calls if "DELETE FROM" in sql]
    assert any("DELETE FROM segments" in sql for sql in delete_sqls)
    assert any("DELETE FROM pages" in sql for sql in delete_sqls)

    first_delete_idx = next(i for i, (sql, _) in enumerate(calls) if "DELETE FROM" in sql)
    progress_idx = next(i for i, (sql, _) in enumerate(calls) if "analysis_progress = 0" in sql)
    assert first_delete_idx < progress_idx
    par.assert_called_once_with(["/tmp/page-1.png"], False, "part01")


def test_analyze_score_empty_imfiles_skips_deletes() -> None:
    calls: list[str] = []

    def fake_execute(sql: str, params: dict | None = None) -> None:
        calls.append(sql)

    with patch("find_segments.db_conn.execute", side_effect=fake_execute):
        analyze_score("part01", [])

    assert not any("DELETE FROM" in sql for sql in calls)
    assert any("analysis_complete = NOW()" in sql for sql in calls)
