"""Delete failed partsets (error IS NOT NULL) for a library user.

Email is not stored — users are Google subject ids in `users.id`.
Run --list first to find your user id.

Usage (on EC2, from repo root):

  docker compose -f docker-compose.prod.yml exec api \\
    python -m app.admin.delete_failed_partsets --list

  docker compose -f docker-compose.prod.yml exec api \\
    python -m app.admin.delete_failed_partsets --user-id YOUR_GOOGLE_SUB --dry-run

  docker compose -f docker-compose.prod.yml exec api \\
    python -m app.admin.delete_failed_partsets --user-id YOUR_GOOGLE_SUB --confirm
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import func, text

from app.db import SessionLocal
from app.models import Partset, User
from app.services.local_cache import get_local_cache
from app.services.partset_admin import delete_partset
from app.services.s3 import delete_object, score_pdf_s3_key


def _list_failed(db) -> None:
    rows = (
        db.query(
            User.id,
            User.name,
            func.count(Partset.id),
        )
        .join(Partset, Partset.user_id == User.id)
        .filter(Partset.error.isnot(None))
        .group_by(User.id, User.name)
        .order_by(User.name)
        .all()
    )
    if not rows:
        print("No failed partsets with a user_id.")
        unowned = db.query(Partset).filter(Partset.error.isnot(None), Partset.user_id.is_(None)).count()
        if unowned:
            print(f"({unowned} failed partset(s) have no user_id — anonymous imports.)")
        return

    print("Failed partsets by user:\n")
    for user_id, name, count in rows:
        print(f"  user_id={user_id!r}  name={name!r}  failed={count}")

    print("\nDetails:\n")
    partsets = (
        db.query(Partset, User.name)
        .outerjoin(User, User.id == Partset.user_id)
        .filter(Partset.error.isnot(None))
        .order_by(Partset.create_ts.desc())
        .all()
    )
    for partset, user_name in partsets:
        print(
            f"  {partset.id}  private={partset.private_id}  "
            f"user={user_name or '(none)'}  error={partset.error}  {partset.title!r}"
        )


def _purge_orphan_score(db, score_id: str) -> bool:
    remaining = db.query(Partset).filter(Partset.score_id == score_id).count()
    if remaining:
        return False
    cache = get_local_cache()
    score_root = cache.score_root(score_id)
    if score_root.is_dir():
        import shutil

        shutil.rmtree(score_root, ignore_errors=True)
    try:
        delete_object(score_pdf_s3_key(score_id))
    except Exception:
        pass
    db.execute(text("DELETE FROM original_pages WHERE score_id = :id"), {"id": score_id})
    db.execute(text("DELETE FROM original_segments WHERE score_id = :id"), {"id": score_id})
    db.execute(text("DELETE FROM scores WHERE id = :id"), {"id": score_id})
    return True


def _delete_for_user(db, user_id: str, *, confirm: bool) -> None:
    partsets = (
        db.query(Partset)
        .filter(Partset.user_id == user_id, Partset.error.isnot(None))
        .order_by(Partset.create_ts)
        .all()
    )
    if not partsets:
        print(f"No failed partsets for user_id={user_id!r}.")
        return

    user = db.get(User, user_id)
    label = user.name if user else user_id
    print(f"{'Deleting' if confirm else 'Would delete'} {len(partsets)} failed partset(s) for {label!r}:\n")
    score_ids: set[str] = set()
    for partset in partsets:
        print(f"  {partset.id}  {partset.private_id}  error={partset.error}  {partset.title!r}")
        if partset.score_id:
            score_ids.add(partset.score_id)

    if not confirm:
        print("\nRe-run with --confirm to delete.")
        return

    for partset in partsets:
        delete_partset(db, partset)

    purged = 0
    for score_id in score_ids:
        if _purge_orphan_score(db, score_id):
            purged += 1
            print(f"  purged orphan score {score_id}")
    db.commit()
    print(f"\nDone. Deleted {len(partsets)} partset(s), purged {purged} orphan score(s).")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Delete failed partsets for a user.")
    parser.add_argument("--list", action="store_true", help="List failed partsets and user ids")
    parser.add_argument("--user-id", help="Google subject id from users.id / partsets.user_id")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted (default)")
    parser.add_argument("--confirm", action="store_true", help="Actually delete")
    args = parser.parse_args(argv)

    if args.confirm and args.dry_run:
        print("Use either --dry-run or --confirm, not both.", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        if args.list:
            _list_failed(db)
            return 0
        if not args.user_id:
            parser.error("Pass --user-id or --list")
        _delete_for_user(db, args.user_id, confirm=args.confirm)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
