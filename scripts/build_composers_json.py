#!/usr/bin/env python3
"""Build frontend/public/data/composers.json for PDF upload autocomplete.

Reads MySQL connection settings from the repo `.env` (MYSQL_* variables).
Popular composers come from the `composers` table (ORDER BY popularity DESC).
Full name list comes from scripts/data/composers_names.txt (or --names-file).
Falls back to scripts/data/composer_popular_seed.txt if MySQL is unreachable.

Usage:
  cd api && uv run python ../scripts/build_composers_json.py

On the EC2 host (MySQL not published on localhost), override the Docker hostname:
  cd api && uv run python ../scripts/build_composers_json.py \\
    --mysql-host "$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' \\
      "$(docker compose -f docker-compose.prod.yml ps -q mysql)")"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV = REPO_ROOT / ".env"
DEFAULT_NAMES = REPO_ROOT / "scripts" / "data" / "composers_names.txt"
SEED_FILE = REPO_ROOT / "scripts" / "data" / "composer_popular_seed.txt"
OUTPUT = REPO_ROOT / "frontend" / "public" / "data" / "composers.json"
POPULAR_LIMIT = 120


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def mysql_settings() -> dict[str, str | int] | None:
    host = os.environ.get("MYSQL_HOST")
    if not host:
        return None
    return {
        "host": host,
        "port": int(os.environ.get("MYSQL_PORT", "3306")),
        "user": os.environ.get("MYSQL_USER", "partifi"),
        "password": os.environ.get("MYSQL_PASSWORD", ""),
        "database": os.environ.get("MYSQL_DATABASE", "partifi"),
    }


def load_names(path: Path) -> list[str]:
    names = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not names:
        raise SystemExit(f"No composer names found in {path}")
    return names


def load_popular_from_db() -> list[str] | None:
    settings = mysql_settings()
    if not settings:
        return None
    try:
        import pymysql
    except ImportError:
        print("pymysql not installed; skipping composers table query", file=sys.stderr)
        return None

    try:
        conn = pymysql.connect(connect_timeout=5, **settings)
    except Exception as exc:
        print(f"MySQL unavailable ({exc}); using seed file", file=sys.stderr)
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
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV, help="Env file with MYSQL_* (default: .env)")
    parser.add_argument("--names-file", type=Path, help="Composer names list (default: scripts/data/composers_names.txt)")
    parser.add_argument("--mysql-host", help="Override MYSQL_HOST from .env")
    parser.add_argument("--mysql-port", type=int, help="Override MYSQL_PORT from .env")
    args = parser.parse_args()

    load_env_file(args.env_file)
    if args.mysql_host:
        os.environ["MYSQL_HOST"] = args.mysql_host
    if args.mysql_port:
        os.environ["MYSQL_PORT"] = str(args.mysql_port)

    names_path = resolve_names_file(args.names_file)
    names = load_names(names_path)
    name_set = set(names)

    popular_source = "mysql"
    popular_raw = load_popular_from_db()
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

    settings = mysql_settings()
    db_label = f"{settings['user']}@{settings['host']}:{settings['port']}/{settings['database']}" if settings else "n/a"
    print(f"Wrote {OUTPUT}")
    print(f"  names: {len(names)} from {names_path}")
    print(f"  popular: {len(popular)} from {popular_source}" + (f" ({db_label})" if popular_source == "mysql" else ""))


if __name__ == "__main__":
    main()
