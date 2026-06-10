#!/usr/bin/env python3
"""One-time import of legacy score/partset data into the new MySQL schema.

Imports content tables only (no users, favorites, donations, or downloads).
Legacy editor/download links keep working because public/private ids are preserved.

Usage:
  cd api && uv run python ../scripts/migrate_legacy_data.py --dry-run
  cd api && uv run python ../scripts/migrate_legacy_data.py --confirm
  cd api && uv run python ../scripts/migrate_legacy_data.py --confirm --verbose
"""

from __future__ import annotations

import argparse
import os
import sys

import pymysql
from pymysql.cursors import DictCursor

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


def _duplicate_keys_in_batch(batch: list[tuple], *, key_index: int = 0) -> dict[object, int]:
    counts: dict[object, int] = {}
    for row in batch:
        key = row[key_index]
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


def _insert_batches(
    *,
    table: str,
    legacy: pymysql.connections.Connection,
    target: pymysql.connections.Connection,
    select_sql: str,
    insert_sql: str,
    cols: list[str],
    pk_index: int = 0,
) -> int:
    key_col = cols[pk_index]
    target_count_before = _count(target, table)
    if VERBOSE:
        _log(f"{table}: target rows before truncate = {target_count_before}")

    with legacy.cursor() as src, target.cursor() as dst:
        dst.execute("SET FOREIGN_KEY_CHECKS=0")
        dst.execute(f"TRUNCATE TABLE `{table}`")
        target_count_after_truncate = _count(target, table)
        if VERBOSE:
            _log(f"{table}: target rows after truncate = {target_count_after_truncate}")

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
                for row in rows:
                    batch.append(tuple(row[c] for c in cols))

                dupes = _duplicate_keys_in_batch(batch, key_index=pk_index)
                if dupes:
                    sample = dict(list(dupes.items())[:5])
                    raise RuntimeError(
                        f"duplicate keys within {table} batch {batch_num}: {sample}"
                    )

                log_batch = VERBOSE and (
                    batch_num <= 5
                    or batch_num % 10000 == 0
                    or (table in ("scores", "partsets") and batch_num <= 20)
                )
                if log_batch:
                    sample_keys = [row[pk_index] for row in batch[:5]]
                    _log(
                        f"{table} batch {batch_num}: size={len(batch)} "
                        f"sample_{key_col}s={sample_keys}"
                    )

                if VERBOSE and batch_num == 1:
                    batch_keys = [row[pk_index] for row in batch]
                    already = _keys_already_on_target(dst, table, key_col, batch_keys)
                    if already:
                        raise RuntimeError(
                            f"{table} batch 1: {len(already)} keys already on target "
                            f"after truncate (sample: {already[:5]})"
                        )

                dst.executemany(insert_sql, batch)
                copied += len(batch)
                batch.clear()
        except Exception as exc:
            target.rollback()
            current = _count(target, table)
            _log(f"FAILED {table} at batch {batch_num}: {exc}")
            _log(f"{table}: target row count after rollback attempt = {current}")
            if batch:
                dupes = _duplicate_keys_in_batch(batch, key_index=pk_index)
                if dupes:
                    _log(f"{table} batch {batch_num} within-batch dupes: {dupes}")
                if VERBOSE:
                    _log(f"{table} batch {batch_num} keys sample: {[r[pk_index] for r in batch[:10]]}")
            raise

    target.commit()
    target_count_final = _count(target, table)
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
        pk_index=0,
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
        pk_index=0,
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

    with legacy.cursor() as src, target.cursor() as dst:
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
    args = parser.parse_args()
    VERBOSE = args.verbose

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
        total = 0
        total += _copy_table(legacy, target, "scores", dry_run=dry_run)
        total += _copy_partsets(legacy, target, dry_run=dry_run)
        for table in DIRECT_TABLES:
            if table == "scores":
                continue
            total += _copy_table(legacy, target, table, dry_run=dry_run)
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
