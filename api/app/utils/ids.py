import random
import string

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Partset, Score

_CHARS = string.ascii_letters + string.digits


def rand_str(length: int = 5) -> str:
    return "".join(random.choice(_CHARS) for _ in range(length))


def gen_score_id(db: Session) -> str:
    while True:
        candidate = rand_str(5)
        exists = db.scalar(select(func.count()).select_from(Score).where(Score.id == candidate))
        if not exists:
            return candidate


def gen_partset_ids(db: Session) -> tuple[str, str]:
    while True:
        public_id = rand_str(5)
        exists = db.scalar(
            select(func.count()).select_from(Partset).where(Partset.id == public_id)
        )
        if not exists:
            break

    while True:
        private_id = rand_str(5)
        exists = db.scalar(
            select(func.count()).select_from(Partset).where(Partset.private_id == private_id)
        )
        if not exists:
            break

    return public_id, private_id
