from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import Favorite, Part, Partset, Score
from app.services.library import list_library


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _sqlite_fk(dbapi_conn, _connection_record) -> None:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    now = datetime.now(UTC)

    for score_id in ("score1", "score2"):
        session.add(
            Score(
                id=score_id,
                num_pages=1,
                import_complete=now,
                convert_complete=now,
                analysis_complete=now,
            )
        )

    for partset_id, private_id in (("pub1", "priv1"), ("pub2", "priv2")):
        session.add(
            Partset(
                id=partset_id,
                private_id=private_id,
                score_id=f"score{partset_id[-1]}",
                title=f"Title {partset_id}",
                composer="Composer",
                parts_ready=True,
                status="paste",
                import_complete=now,
                convert_complete=now,
                analysis_complete=now,
            )
        )
        session.add(
            Favorite(
                partset_id=partset_id,
                user_id="user1",
                admin=True,
                ts=now,
            )
        )
        session.add(
            Part(
                partset_id=partset_id,
                tag="violin",
                spacing=0.1,
                combined=False,
                file_name="violin.pdf",
            )
        )
        session.add(
            Part(
                partset_id=partset_id,
                tag="cello",
                spacing=0.1,
                combined=False,
                file_name="cello.pdf",
            )
        )

    session.commit()
    return session


def test_list_library_returns_parts_for_all_partsets(db: Session) -> None:
    items = list_library(db, "user1")
    assert len(items) == 2
    tags_by_partset = {item["partset_id"]: {part["tag"] for part in item["parts"]} for item in items}
    assert tags_by_partset["pub1"] == {"violin", "cello"}
    assert tags_by_partset["pub2"] == {"violin", "cello"}


def test_list_library_empty_when_no_favorites(db: Session) -> None:
    assert list_library(db, "nobody") == []
