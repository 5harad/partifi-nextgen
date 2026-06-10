#!/usr/bin/env python3
"""Build frontend/public/data/composers.json from legacy composer names + popularity.

Popular list (priority order for autocomplete):
  1. Legacy MySQL `composers` table ordered by `popularity` DESC (real Partifi usage),
     when LEGACY_MYSQL_* env vars are set and the tunnel/DB is reachable.
  2. Otherwise scripts/data/composer_popular_seed.txt (one composer per line, highest first).

Full name list always comes from legacy setup/composers/composers.txt (or --names-file).

Usage:
  python scripts/build_composers_json.py
  LEGACY_MYSQL_HOST=127.0.0.1 LEGACY_MYSQL_PORT=3307 ... python scripts/build_composers_json.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NAMES = REPO_ROOT / "scripts" / "data" / "composers_names.txt"
SEED_FILE = REPO_ROOT / "scripts" / "data" / "composer_popular_seed.txt"
OUTPUT = REPO_ROOT / "frontend" / "public" / "data" / "composers.json"
POPULAR_LIMIT = 120


def load_names(path: Path) -> list[str]:
    names = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not names:
        raise SystemExit(f"No composer names found in {path}")
    return names


def load_popular_from_legacy() -> list[str] | None:
    host = os.environ.get("LEGACY_MYSQL_HOST")
    if not host:
        return None
    try:
        import pymysql
    except ImportError:
        print("pymysql not installed; skipping legacy popularity query", file=sys.stderr)
        return None

    port = int(os.environ.get("LEGACY_MYSQL_PORT", "3306"))
    user = os.environ.get("LEGACY_MYSQL_USER", "partifi")
    password = os.environ.get("LEGACY_MYSQL_PASSWORD", "")
    database = os.environ.get("LEGACY_MYSQL_DATABASE", "partifi")

    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            connect_timeout=5,
        )
    except Exception as exc:
        print(f"Legacy MySQL unavailable ({exc}); using seed file", file=sys.stderr)
        return None

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT composer FROM composers ORDER BY popularity DESC, composer LIMIT %s",
                (POPULAR_LIMIT,),
            )
            rows = [row[0] for row in cur.fetchall() if row[0]]
        return rows or None
    finally:
        conn.close()


def load_popular_from_seed() -> list[str]:
    if not SEED_FILE.is_file():
        raise SystemExit(f"Missing seed file: {SEED_FILE}")
    return [line.strip() for line in SEED_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]


def resolve_names_file(explicit: Path | None) -> Path:
    if explicit:
        return explicit
    if DEFAULT_NAMES.is_file():
        return DEFAULT_NAMES
    raise SystemExit(f"Composer names file not found: {DEFAULT_NAMES}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build composers.json for frontend autocomplete")
    parser.add_argument("--names-file", type=Path, help="Source composers.txt (default: legacy repo path)")
    args = parser.parse_args()

    names_path = resolve_names_file(args.names_file)
    names = load_names(names_path)
    name_set = set(names)

    popular_source = "legacy-mysql"
    popular_raw = load_popular_from_legacy()
    if not popular_raw:
        popular_source = "seed-file"
        popular_raw = load_popular_from_seed()

    popular: list[str] = []
    seen: set[str] = set()
    for composer in popular_raw:
        if composer in name_set and composer not in seen:
            popular.append(composer)
            seen.add(composer)

    payload = {"names": names, "popular": popular}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print(f"Wrote {OUTPUT}")
    print(f"  names: {len(names)} from {names_path}")
    print(f"  popular: {len(popular)} from {popular_source}")


if __name__ == "__main__":
    main()
