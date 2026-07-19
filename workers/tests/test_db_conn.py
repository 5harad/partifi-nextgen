from unittest.mock import MagicMock, patch

import db_conn


def _mock_engine_with_rows(rows: list[dict]) -> tuple[MagicMock, MagicMock]:
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    result = MagicMock()
    result.mappings.return_value.all.return_value = rows
    connection.execute.return_value = result
    return engine, connection


def test_finalize_part_generation_updates_names_and_ready_atomically() -> None:
    engine, connection = _mock_engine_with_rows(
        [
            {"tag": "глас", "combined": False},
            {"tag": "китара", "combined": False},
        ]
    )
    file_names = {
        "глас": "glas-111111111111.pdf",
        "китара": "kitara-222222222222.pdf",
    }

    with patch.object(db_conn, "engine", engine):
        published = db_conn.finalize_part_generation(
            "zafrq-jmday",
            snapshot={("глас", False), ("китара", False)},
            file_names=file_names,
        )

    assert published is True
    assert connection.execute.call_count == 3
    update_params = connection.execute.call_args_list[1].args[1]
    assert {row["file_name"] for row in update_params} == set(file_names.values())


def test_finalize_part_generation_rejects_changed_part_rows() -> None:
    engine, connection = _mock_engine_with_rows(
        [{"tag": "renamed", "combined": False}]
    )

    with patch.object(db_conn, "engine", engine):
        published = db_conn.finalize_part_generation(
            "partset-a",
            snapshot={("violin", False)},
            file_names={"violin": "violin-111111111111.pdf"},
        )

    assert published is False
    assert connection.execute.call_count == 2
    reset_query = str(connection.execute.call_args_list[1].args[0])
    assert "paste_start = NULL" in reset_query
    assert "parts_ready = 0" in reset_query


def test_finalize_part_generation_rejects_empty_partset_without_empty_batch() -> None:
    engine, connection = _mock_engine_with_rows([])

    with patch.object(db_conn, "engine", engine):
        published = db_conn.finalize_part_generation(
            "partset-a",
            snapshot=set(),
            file_names={},
        )

    assert published is False
    assert connection.execute.call_count == 2
