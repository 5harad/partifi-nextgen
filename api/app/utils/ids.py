from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Partset, Score
from pipeline.ids import rand_partifi_id


def gen_score_id(db: Session) -> str:
    while True:
        candidate = rand_partifi_id()
        exists = db.scalar(select(func.count()).select_from(Score).where(Score.id == candidate))
        if not exists:
            return candidate


def partset_id_in_use(db: Session, candidate: str) -> bool:
    """True if candidate is already a public id or private id on any partset."""
    in_public = db.scalar(
        select(func.count()).select_from(Partset).where(Partset.id == candidate)
    )
    if in_public:
        return True
    in_private = db.scalar(
        select(func.count()).select_from(Partset).where(Partset.private_id == candidate)
    )
    return bool(in_private)


def gen_partset_ids(db: Session) -> tuple[str, str]:
    while True:
        public_id = rand_partifi_id()
        if not partset_id_in_use(db, public_id):
            break

    while True:
        private_id = rand_partifi_id()
        if private_id == public_id:
            continue
        if not partset_id_in_use(db, private_id):
            break

    return public_id, private_id
