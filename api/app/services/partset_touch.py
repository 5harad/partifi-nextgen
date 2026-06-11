from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Partset


def touch_partset_access(db: Session, partset: Partset) -> None:
    partset.last_access = datetime.utcnow()
    db.commit()
