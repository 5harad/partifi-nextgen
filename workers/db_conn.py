from sqlalchemy import create_engine, text

from config import get_settings

_settings = get_settings()
engine = create_engine(_settings.database_url, pool_pre_ping=True)


def execute(query: str, params: dict | None = None) -> None:
    with engine.begin() as conn:
        conn.execute(text(query), params or {})


def fetchone(query: str, params: dict | None = None):
    with engine.connect() as conn:
        return conn.execute(text(query), params or {}).fetchone()


def fetchall(query: str, params: dict | None = None):
    with engine.connect() as conn:
        return conn.execute(text(query), params or {}).fetchall()


def finalize_part_generation(
    partset_id: str,
    *,
    snapshot: set[tuple[str, bool]],
    file_names: dict[str, str],
) -> bool:
    """Atomically publish generated filenames if the part rows did not change."""
    with engine.begin() as conn:
        current_rows = (
            conn.execute(
                text(
                    "SELECT tag, combined FROM parts "
                    "WHERE partset_id = :partset_id FOR UPDATE"
                ),
                {"partset_id": partset_id},
            )
            .mappings()
            .all()
        )
        current = {(str(row["tag"]), bool(row["combined"])) for row in current_rows}
        if (
            not file_names
            or current != snapshot
            or set(file_names) != {tag for tag, _ in snapshot}
        ):
            conn.execute(
                text(
                    "UPDATE partsets SET status = 'analysis', parts_ready = 0, "
                    "cut_start = NULL, cut_complete = NULL, cut_progress = 0, "
                    "paste_start = NULL, paste_complete = NULL, paste_progress = 0, "
                    "last_job_id = NULL WHERE id = :id"
                ),
                {"id": partset_id},
            )
            return False

        conn.execute(
            text(
                "UPDATE parts SET file_name = :file_name "
                "WHERE partset_id = :partset_id AND tag = :tag"
            ),
            [
                {
                    "file_name": file_name,
                    "partset_id": partset_id,
                    "tag": tag,
                }
                for tag, file_name in file_names.items()
            ],
        )
        conn.execute(
            text(
                "UPDATE partsets SET paste_complete = NOW(), parts_ready = 1, mod_ts = NOW(), "
                "error = NULL, error_message = NULL, error_ts = NULL, last_job_id = NULL "
                "WHERE id = :id"
            ),
            {"id": partset_id},
        )
    return True
