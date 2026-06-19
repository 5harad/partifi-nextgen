"""Delete all partsets and related rows for a ghost / junk score id.

Use when a score row (e.g. migration cluster aX38M) has no archived PDF and
partsets should be removed in bulk.

Usage (on EC2, from repo root):

  docker compose -f docker-compose.prod.yml exec api \\
    python -m app.admin.purge_score_cluster --score-id aX38M --dry-run

  docker compose -f docker-compose.prod.yml exec api \\
    python -m app.admin.purge_score_cluster --score-id aX38M --confirm
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime

from sqlalchemy import text

from app.db import SessionLocal
from app.models import Score
from app.services.local_cache import get_local_cache
from app.services.s3 import delete_object, score_pdf_s3_key

DEFAULT_SCORE_ID = "aX38M"
DEFAULT_BATCH_SIZE = 5000


def _scalar(db, sql: str, **params) -> int:
    value = db.execute(text(sql), params).scalar()
    return int(value or 0)


def _count_cluster(db, score_id: str) -> dict[str, int]:
    return {
        "partsets": _scalar(
            db,
            "SELECT COUNT(*) FROM partsets WHERE score_id = :score_id",
            score_id=score_id,
        ),
        "segments": _scalar(
            db,
            """
            SELECT COUNT(*) FROM segments s
            JOIN partsets p ON p.id = s.partset_id
            WHERE p.score_id = :score_id
            """,
            score_id=score_id,
        ),
        "pages": _scalar(
            db,
            """
            SELECT COUNT(*) FROM pages pg
            JOIN partsets p ON p.id = pg.partset_id
            WHERE p.score_id = :score_id
            """,
            score_id=score_id,
        ),
        "parts": _scalar(
            db,
            """
            SELECT COUNT(*) FROM parts pt
            JOIN partsets p ON p.id = pt.partset_id
            WHERE p.score_id = :score_id
            """,
            score_id=score_id,
        ),
        "breaks": _scalar(
            db,
            """
            SELECT COUNT(*) FROM breaks b
            JOIN partsets p ON p.id = b.partset_id
            WHERE p.score_id = :score_id
            """,
            score_id=score_id,
        ),
        "favorites": _scalar(
            db,
            """
            SELECT COUNT(*) FROM favorites f
            JOIN partsets p ON p.id = f.partset_id
            WHERE p.score_id = :score_id
            """,
            score_id=score_id,
        ),
        "downloads": _scalar(
            db,
            """
            SELECT COUNT(*) FROM downloads d
            JOIN partsets p ON p.id = d.partset_id
            WHERE p.score_id = :score_id
            """,
            score_id=score_id,
        ),
        "original_pages": _scalar(
            db,
            "SELECT COUNT(*) FROM original_pages WHERE score_id = :score_id",
            score_id=score_id,
        ),
        "original_segments": _scalar(
            db,
            "SELECT COUNT(*) FROM original_segments WHERE score_id = :score_id",
            score_id=score_id,
        ),
    }


def _print_summary(db, score_id: str) -> None:
    score = db.get(Score, score_id)
    counts = _count_cluster(db, score_id)
    print(f"Score cluster purge summary for {score_id!r}\n")
    if score is None:
        print("  scores row: not found")
    else:
        print(
            "  scores row:"
            f" s3={score.s3} file_size={score.file_size}"
            f" num_pages={score.num_pages} convert_complete={score.convert_complete}"
        )
    for key, value in counts.items():
        print(f"  {key}: {value}")

    row = db.execute(
        text(
            """
            SELECT MIN(create_ts) AS oldest, MAX(create_ts) AS newest
            FROM partsets
            WHERE score_id = :score_id
            """
        ),
        {"score_id": score_id},
    ).mappings().first()
    if row and row["oldest"]:
        print(f"  partset create_ts range: {row['oldest']} .. {row['newest']}")

    recent = _scalar(
        db,
        """
        SELECT COUNT(*) FROM partsets
        WHERE score_id = :score_id AND create_ts >= :cutoff
        """,
        score_id=score_id,
        cutoff=datetime(2026, 6, 1),
    )
    print(f"  partsets created since 2026-06-01: {recent}")


def _delete_children_for_partsets(db, partset_ids: tuple[str, ...]) -> None:
    if not partset_ids:
        return
    placeholders = ", ".join(f":id{i}" for i in range(len(partset_ids)))
    params = {f"id{i}": partset_id for i, partset_id in enumerate(partset_ids)}
    for table, column in (
        ("segments", "partset_id"),
        ("breaks", "partset_id"),
        ("parts", "partset_id"),
        ("pages", "partset_id"),
        ("favorites", "partset_id"),
        ("downloads", "partset_id"),
    ):
        db.execute(
            text(f"DELETE FROM {table} WHERE {column} IN ({placeholders})"),
            params,
        )


def _purge_score_cluster(
    db,
    score_id: str,
    *,
    batch_size: int,
    confirm: bool,
) -> None:
    if not confirm:
        _print_summary(db, score_id)
        print("\nRe-run with --confirm to delete.")
        return

    deleted_partsets = 0
    batch_num = 0
    while True:
        rows = db.execute(
            text(
                """
                SELECT id FROM partsets
                WHERE score_id = :score_id
                ORDER BY create_ts
                LIMIT :limit
                """
            ),
            {"score_id": score_id, "limit": batch_size},
        ).all()
        if not rows:
            break
        partset_ids = tuple(row[0] for row in rows)
        batch_num += 1
        _delete_children_for_partsets(db, partset_ids)
        db.execute(
            text("DELETE FROM partsets WHERE id IN (" + ", ".join(f":id{i}" for i in range(len(partset_ids))) + ")"),
            {f"id{i}": partset_id for i, partset_id in enumerate(partset_ids)},
        )
        db.commit()
        deleted_partsets += len(partset_ids)
        print(f"  batch {batch_num}: deleted {len(partset_ids)} partset(s) ({deleted_partsets} total)")

    db.execute(text("DELETE FROM original_pages WHERE score_id = :score_id"), {"score_id": score_id})
    db.execute(text("DELETE FROM original_segments WHERE score_id = :score_id"), {"score_id": score_id})
    db.execute(text("DELETE FROM scores WHERE id = :score_id"), {"score_id": score_id})
    db.commit()

    cache = get_local_cache()
    score_root = cache.score_root(score_id)
    if score_root.is_dir():
        shutil.rmtree(score_root, ignore_errors=True)
        print(f"  removed local cache dir {score_root}")

    try:
        delete_object(score_pdf_s3_key(score_id))
        print(f"  removed S3 object {score_pdf_s3_key(score_id)}")
    except Exception as exc:
        print(f"  S3 score PDF delete skipped: {exc}")

    remaining = _count_cluster(db, score_id)
    print(
        f"\nDone. Deleted {deleted_partsets} partset(s) for score {score_id!r}."
        f" Remaining partsets: {remaining['partsets']}."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Delete all partsets and related rows tied to a score id.",
    )
    parser.add_argument(
        "--score-id",
        default=DEFAULT_SCORE_ID,
        help=f"Score id to purge (default: {DEFAULT_SCORE_ID})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Partsets deleted per batch (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show counts only (default when --confirm is omitted)",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually delete rows",
    )
    args = parser.parse_args(argv)

    score_id = args.score_id.strip()
    if not score_id:
        print("score-id must not be empty.", file=sys.stderr)
        return 1
    if args.batch_size < 1:
        print("batch-size must be >= 1.", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        _purge_score_cluster(
            db,
            score_id,
            batch_size=args.batch_size,
            confirm=args.confirm,
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
