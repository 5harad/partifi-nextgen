#!/usr/bin/env python3
"""One-time import of legacy score/partset data into the new MySQL schema.

Imports content tables only (no users, favorites, donations, or downloads).
Legacy editor/download links keep working because public/private ids are preserved.

Usage:
  cd api && uv run python ../scripts/migrate_legacy_data.py --dry-run
  cd api && uv run python ../scripts/migrate_legacy_data.py --confirm
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


def _connect(prefix: str) -> pymysql.connections.Connection:
    host = os.environ[f"{prefix}_MYSQL_HOST"]
    return pymysql.connect(
        host=host,
        port=int(os.environ.get(f"{prefix}_MYSQL_PORT", "3306")),
        user=os.environ.get(f"{prefix}_MYSQL_USER", "partifi"),
        password=os.environ[f"{prefix}_MYSQL_PASSWORD"],
        database=os.environ.get(f"{prefix}_MYSQL_DATABASE", "partifi"),
        charset="utf8mb4",
        cursorclass=DictCursor,
    )


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

    with legacy.cursor() as src, target.cursor() as dst:
        dst.execute("SET FOREIGN_KEY_CHECKS=0")
        dst.execute(f"TRUNCATE TABLE `{table}`")
        src.execute(f"SELECT {col_list} FROM `{table}`")
        batch: list[tuple] = []
        copied = 0
        while True:
            rows = src.fetchmany(500)
            if not rows:
                break
            for row in rows:
                batch.append(tuple(row[c] for c in cols))
            dst.executemany(insert_sql, batch)
            copied += len(batch)
            batch.clear()
    target.commit()
    print(f"  {table}: copied {copied} rows")
    return copied


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

    with legacy.cursor() as src, target.cursor() as dst:
        dst.execute("SET FOREIGN_KEY_CHECKS=0")
        dst.execute("TRUNCATE TABLE partsets")
        src.execute(f"SELECT {col_list} FROM partsets")
        batch: list[tuple] = []
        copied = 0
        while True:
            rows = src.fetchmany(500)
            if not rows:
                break
            for row in rows:
                batch.append(tuple(row[c] for c in cols))
            dst.executemany(insert_sql, batch)
            copied += len(batch)
            batch.clear()
    target.commit()
    print(f"  partsets: copied {copied} rows")
    return copied


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

    with legacy.cursor() as src, target.cursor() as dst:
        dst.execute("SET FOREIGN_KEY_CHECKS=0")
        dst.execute("TRUNCATE TABLE breaks")
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print row counts only")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Truncate target content tables and import from legacy",
    )
    args = parser.parse_args()

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
