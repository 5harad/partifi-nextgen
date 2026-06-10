#!/usr/bin/env python3
"""One-time import of legacy score/partset data into the new MySQL schema.

Imports content tables only (no users, favorites, donations, or downloads).
Legacy editor/download links keep working because public/private ids are preserved.

Requires case-sensitive string id columns (utf8mb4_bin) on the target database.
Run scripts/alter_case_sensitive_ids.sql before import if upgrading an older schema.

Usage:
  cd api && uv run python ../scripts/migrate_legacy_data.py --dry-run
  cd api && uv run python ../scripts/migrate_legacy_data.py --confirm
  cd api && uv run python ../scripts/migrate_legacy_data.py --confirm --verbose
  cd api && uv run python ../scripts/migrate_legacy_data.py --confirm --from-table original_pages
"""

from __future__ import annotations

import argparse
import os
import sys

import pymysql
from pymysql.cursors import DictCursor, SSDictCursor

DIRECT_TABLES = (
    "scores",
    "original_pages",
    "original_segments",
    "pages",
    "segments",
    "parts",
    "imslp_info",
    "composers",
)

PARTSET_COLUMNS = (
    "id",
    "private_id",
    "score_id",
    "imslp_id",
    "tmpdir",
    "create_ts",
    "mod_ts",
    "last_access",
    "parts_ready",
    "title",
    "composer",
    "publisher",
    "copyright",
    "user_id",
    "num_downloads",
    "status",
    "error",
    "import_start",
    "import_complete",
    "import_progress",
    "convert_start",
    "convert_complete",
    "convert_progress",
    "analysis_start",
    "analysis_complete",
    "analysis_progress",
    "cut_start",
    "cut_complete",
    "cut_progress",
    "paste_start",
    "paste_complete",
    "paste_progress",
)

# Target columns that must use utf8mb4_bin so legacy ids differing only by case import.
REQUIRED_BIN_COLUMNS = (
    ("scores", "id"),
    ("partsets", "id"),
    ("partsets", "private_id"),
)

IMPORT_ORDER = (
    "scores",
    "partsets",
    "original_pages",
    "original_segments",
    "pages",
    "segments",
    "parts",
    "imslp_info",
    "composers",
    "breaks",
)

# Primary key column names per table (composite where applicable).
TABLE_PK_COLUMNS: dict[str, tuple[str, ...]] = {
    "scores": ("id",),
    "partsets": ("id",),
    "original_pages": ("score_id", "page"),
    "original_segments": ("id",),
    "pages": ("partset_id", "page"),
    "segments": ("id",),
    "parts": ("partset_id", "tag"),
    "imslp_info": ("id",),
    "composers": ("composer",),
    "breaks": ("id",),
}

VERBOSE = False


def _log(msg: str) -> None:
    print(msg, flush=True)


def _connect(prefix: str) -> pymysql.connections.Connection:
    host = os.environ[f"{prefix}_MYSQL_HOST"]
    port = int(os.environ.get(f"{prefix}_MYSQL_PORT", "3306"))
    database = os.environ.get(f"{prefix}_MYSQL_DATABASE", "partifi")
    conn = pymysql.connect(
        host=host,
        port=port,
        user=os.environ.get(f"{prefix}_MYSQL_USER", "partifi"),
        password=os.environ[f"{prefix}_MYSQL_PASSWORD"],
        database=database,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )
    if VERBOSE:
        _log(f"connected {prefix}: {host}:{port}/{database}")
    return conn


def _count(conn: pymysql.connections.Connection, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS n FROM `{table}`")
        row = cur.fetchone()
        return int(row["n"])


def _column_collation(conn: pymysql.connections.Connection, table: str, column: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COLLATION_NAME
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
              AND COLUMN_NAME = %s
            """,
            (table, column),
        )
        row = cur.fetchone()
        return row["COLLATION_NAME"] if row else None


def _verify_target_bin_collations(target: pymysql.connections.Connection) -> None:
    bad: list[str] = []
    for table, column in REQUIRED_BIN_COLUMNS:
        collation = _column_collation(target, table, column)
        if collation != "utf8mb4_bin":
            bad.append(f"{table}.{column} (got {collation!r})")
    if bad:
        raise RuntimeError(
            "Target id columns must use utf8mb4_bin for case-sensitive legacy ids. "
            f"Fix: scripts/alter_case_sensitive_ids.sql. Bad: {', '.join(bad)}"
        )


def _report_legacy_case_id_groups(
    legacy: pymysql.connections.Connection, table: str, *, id_col: str = "id"
) -> list[dict]:
    with legacy.cursor() as cur:
        cur.execute(
            f"""
            SELECT LOWER(`{id_col}`) AS norm, COUNT(*) AS c,
                   GROUP_CONCAT(`{id_col}` SEPARATOR '|') AS variants
            FROM `{table}`
            GROUP BY LOWER(`{id_col}`)
            HAVING COUNT(*) > 1
            ORDER BY c DESC
            LIMIT 10
            """
        )
        return list(cur.fetchall())


def _column_names(conn: pymysql.connections.Connection, table: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(f"SHOW COLUMNS FROM `{table}`")
        return [row["Field"] for row in cur.fetchall()]


def _shared_columns(
    legacy: pymysql.connections.Connection,
    target: pymysql.connections.Connection,
    table: str,
) -> list[str]:
    target_cols = set(_column_names(target, table))
    if table == "partsets":
        return [c for c in PARTSET_COLUMNS if c in target_cols]
    return [c for c in _column_names(legacy, table) if c in target_cols]


def _pk_indices(cols: list[str], pk_col_names: tuple[str, ...]) -> tuple[int, ...]:
    return tuple(cols.index(name) for name in pk_col_names)


def _row_pk(batch_row: tuple, pk_indices: tuple[int, ...]) -> tuple:
    return tuple(batch_row[i] for i in pk_indices)


def _duplicate_keys_in_batch(
    batch: list[tuple], *, pk_indices: tuple[int, ...]
) -> dict[tuple, int]:
    counts: dict[tuple, int] = {}
    for row in batch:
        key = _row_pk(row, pk_indices)
        counts[key] = counts.get(key, 0) + 1
    return {key: count for key, count in counts.items() if count > 1}


def _keys_already_on_target(
    dst: pymysql.cursors.Cursor,
    table: str,
    key_col: str,
    keys: list[object],
) -> list[object]:
    if not keys:
        return []
    placeholders = ", ".join(["%s"] * len(keys))
    dst.execute(
        f"SELECT `{key_col}` FROM `{table}` WHERE `{key_col}` IN ({placeholders})",
        keys,
    )
    return [row[key_col] for row in dst.fetchall()]


def _pk_col_names(table: str, cols: list[str]) -> tuple[str, ...]:
    names = TABLE_PK_COLUMNS.get(table, ("id",))
    missing = [n for n in names if n not in cols]
    if missing:
        raise RuntimeError(f"{table}: PK columns {missing} not in import column list {cols}")
    return names


def _insert_batches(
    *,
    table: str,
    legacy: pymysql.connections.Connection,
    target: pymysql.connections.Connection,
    select_sql: str,
    insert_sql: str,
    cols: list[str],
    pk_col_names: tuple[str, ...],
    legacy_count: int | None = None,
) -> int:
    pk_indices = _pk_indices(cols, pk_col_names)
    single_pk_col = pk_col_names[0] if len(pk_col_names) == 1 else None
    target_count_before = _count(target, table)
    if VERBOSE:
        _log(f"{table}: target rows before truncate = {target_count_before}")

    # SSDictCursor streams from legacy — default Cursor buffers the full SELECT
    # in memory on execute(), which OOM-kills large tables (e.g. segments).
    with legacy.cursor(SSDictCursor) as src, target.cursor() as dst:
        dst.execute("SET FOREIGN_KEY_CHECKS=0")
        dst.execute(f"TRUNCATE TABLE `{table}`")
        target_count_after_truncate = _count(target, table)
        if VERBOSE:
            _log(f"{table}: target rows after truncate = {target_count_after_truncate}")

        if VERBOSE:
            _log(f"{table}: starting legacy SELECT (streaming cursor)…")
        src.execute(select_sql)
        batch: list[tuple] = []
        copied = 0
        batch_num = 0
        try:
            while True:
                rows = src.fetchmany(500)
                if not rows:
                    break
                batch_num += 1
                batch.clear()
                for row in rows:
                    batch.append(tuple(row[c] for c in cols))

                dupes = _duplicate_keys_in_batch(batch, pk_indices=pk_indices)
                if dupes:
                    sample = dict(list(dupes.items())[:5])
                    raise RuntimeError(
                        f"duplicate PKs within {table} batch {batch_num}: {sample}"
                    )

                log_batch = VERBOSE and (
                    batch_num <= 5
                    or batch_num % 10000 == 0
                    or (table in ("scores", "partsets") and batch_num <= 20)
                )
                if log_batch:
                    sample_keys = [_row_pk(row, pk_indices) for row in batch[:5]]
                    _log(
                        f"{table} batch {batch_num}: size={len(batch)} "
                        f"sample_pks={sample_keys}"
                    )

                if VERBOSE and batch_num == 1 and single_pk_col:
                    batch_keys = [row[pk_indices[0]] for row in batch]
                    already = _keys_already_on_target(dst, table, single_pk_col, batch_keys)
                    if already:
                        raise RuntimeError(
                            f"{table} batch 1: {len(already)} keys already on target "
                            f"after truncate (sample: {already[:5]})"
                        )

                dst.executemany(insert_sql, batch)
                copied += len(batch)
        except Exception as exc:
            target.rollback()
            current = _count(target, table)
            _log(f"FAILED {table} at batch {batch_num}: {exc}")
            _log(f"{table}: target row count after rollback attempt = {current}")
            if batch:
                dupes = _duplicate_keys_in_batch(batch, pk_indices=pk_indices)
                if dupes:
                    _log(f"{table} batch {batch_num} within-batch dupes: {dupes}")
                if VERBOSE:
                    _log(
                        f"{table} batch {batch_num} pk sample: "
                        f"{[_row_pk(r, pk_indices) for r in batch[:10]]}"
                    )
            raise

    target.commit()
    target_count_final = _count(target, table)
    if legacy_count is not None and target_count_final != legacy_count:
        raise RuntimeError(
            f"{table}: legacy has {legacy_count} rows but target has {target_count_final}"
        )
    if target_count_final != copied:
        raise RuntimeError(
            f"{table}: inserted {copied} rows but target count is {target_count_final}"
        )
    print(f"  {table}: copied {copied} rows")
    return copied


def _copy_table(
    legacy: pymysql.connections.Connection,
    target: pymysql.connections.Connection,
    table: str,
    *,
    dry_run: bool,
) -> int:
    legacy_count = _count(legacy, table)
    if dry_run:
        print(f"  {table}: {legacy_count} rows")
        return legacy_count

    cols = _shared_columns(legacy, target, table)
    col_list = ", ".join(f"`{c}`" for c in cols)
    placeholders = ", ".join(["%s"] * len(cols))
    insert_sql = f"INSERT INTO `{table}` ({col_list}) VALUES ({placeholders})"

    return _insert_batches(
        table=table,
        legacy=legacy,
        target=target,
        select_sql=f"SELECT {col_list} FROM `{table}`",
        insert_sql=insert_sql,
        cols=cols,
        pk_col_names=_pk_col_names(table, cols),
        legacy_count=legacy_count,
    )


def _copy_partsets(
    legacy: pymysql.connections.Connection,
    target: pymysql.connections.Connection,
    *,
    dry_run: bool,
) -> int:
    legacy_count = _count(legacy, "partsets")
    if dry_run:
        print(f"  partsets: {legacy_count} rows")
        return legacy_count

    cols = [c for c in PARTSET_COLUMNS if c in set(_column_names(legacy, "partsets"))]
    col_list = ", ".join(f"`{c}`" for c in cols)
    placeholders = ", ".join(["%s"] * len(cols))
    insert_sql = f"INSERT INTO partsets ({col_list}) VALUES ({placeholders})"

    return _insert_batches(
        table="partsets",
        legacy=legacy,
        target=target,
        select_sql=f"SELECT {col_list} FROM partsets",
        insert_sql=insert_sql,
        cols=cols,
        pk_col_names=("id",),
        legacy_count=legacy_count,
    )


def _copy_breaks(
    legacy: pymysql.connections.Connection,
    target: pymysql.connections.Connection,
    *,
    dry_run: bool,
) -> int:
    legacy_count = _count(legacy, "breaks")
    if dry_run:
        print(f"  breaks: {legacy_count} rows")
        return legacy_count

    if VERBOSE:
        _log(f"breaks: target rows before truncate = {_count(target, 'breaks')}")

    with legacy.cursor(SSDictCursor) as src, target.cursor() as dst:
        dst.execute("SET FOREIGN_KEY_CHECKS=0")
        dst.execute("TRUNCATE TABLE breaks")
        if VERBOSE:
            _log(f"breaks: target rows after truncate = {_count(target, 'breaks')}")
        src.execute("SELECT partset_id, tag, `break` FROM breaks")
        rows = src.fetchall()
        if rows:
            dst.executemany(
                "INSERT INTO breaks (partset_id, tag, `break`) VALUES (%s, %s, %s)",
                [(r["partset_id"], r["tag"], r["break"]) for r in rows],
            )
    target.commit()
    final = _count(target, "breaks")
    if final != legacy_count:
        raise RuntimeError(f"breaks: legacy has {legacy_count} rows but target has {final}")
    print(f"  breaks: copied {legacy_count} rows")
    return legacy_count


def main() -> int:
    global VERBOSE

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print row counts only")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Truncate target content tables and import from legacy",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Log connection info, truncate counts, and per-batch details",
    )
    parser.add_argument(
        "--from-table",
        metavar="TABLE",
        choices=IMPORT_ORDER,
        help="Resume import at this table (skip earlier tables; e.g. original_pages)",
    )
    args = parser.parse_args()
    VERBOSE = args.verbose
    from_table = args.from_table

    if not args.dry_run and not args.confirm:
        print("Pass --dry-run to inspect counts or --confirm to import.", file=sys.stderr)
        return 1

    for var in ("LEGACY_MYSQL_HOST", "LEGACY_MYSQL_PASSWORD", "TARGET_MYSQL_PASSWORD"):
        if var not in os.environ:
            print(f"Missing env var: {var}", file=sys.stderr)
            return 1

    if "TARGET_MYSQL_HOST" not in os.environ:
        os.environ["TARGET_MYSQL_HOST"] = "127.0.0.1"

    dry_run = args.dry_run
    print("Connecting to legacy and target MySQL…")
    legacy = _connect("LEGACY")
    target = _connect("TARGET")

    try:
        print("Import plan (content tables only; users/favorites skipped):")
        if not dry_run:
            _verify_target_bin_collations(target)
            for table, id_col in (("scores", "id"), ("partsets", "id")):
                groups = _report_legacy_case_id_groups(legacy, table, id_col=id_col)
                if groups:
                    _log(
                        f"Note: legacy {table} has ids differing only by case "
                        f"({len(groups)}+ groups; showing up to 10). "
                        "All variants will be preserved (utf8mb4_bin)."
                    )
                    for row in groups:
                        _log(f"  {row['variants']}")
        def _skip(table: str) -> bool:
            if not from_table:
                return False
            if IMPORT_ORDER.index(table) < IMPORT_ORDER.index(from_table):
                print(f"  {table}: skipped (--from-table {from_table})")
                return True
            return False

        total = 0
        if not _skip("scores"):
            total += _copy_table(legacy, target, "scores", dry_run=dry_run)
        if not _skip("partsets"):
            total += _copy_partsets(legacy, target, dry_run=dry_run)
        for table in DIRECT_TABLES:
            if table == "scores":
                continue
            if _skip(table):
                continue
            total += _copy_table(legacy, target, table, dry_run=dry_run)
        if not _skip("breaks"):
            total += _copy_breaks(legacy, target, dry_run=dry_run)

        if dry_run:
            print(f"Total rows to import: {total}")
        else:
            print("Import complete.")
    finally:
        legacy.close()
        target.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
