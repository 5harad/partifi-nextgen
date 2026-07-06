from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import Favorite, Part, Partset, Score
from app.services.library import claim_partset_for_user, list_library, update_favorite


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
    assert all(item["imslp_id"] is None for item in items)


def test_list_library_includes_imslp_id(db: Session) -> None:
    partset = db.query(Partset).filter(Partset.id == "pub1").first()
    assert partset is not None
    partset.imslp_id = "33421"
    db.commit()

    items = list_library(db, "user1")
    pub1 = next(item for item in items if item["partset_id"] == "pub1")
    assert pub1["imslp_id"] == "33421"


def test_list_library_empty_when_no_favorites(db: Session) -> None:
    assert list_library(db, "nobody") == []


def test_claim_partset_sets_user_id_only_when_unassigned(db: Session) -> None:
    partset = db.query(Partset).filter(Partset.id == "pub1").first()
    assert partset is not None
    partset.user_id = "alice"
    db.commit()

    claim_partset_for_user(db, partset, "bob")
    db.commit()

    db.refresh(partset)
    assert partset.user_id == "alice"
    favorite = (
        db.query(Favorite)
        .filter(Favorite.partset_id == "pub1", Favorite.user_id == "bob")
        .one()
    )
    assert favorite.admin is True


def test_claim_partset_assigns_user_id_when_null(db: Session) -> None:
    partset = db.query(Partset).filter(Partset.id == "pub1").first()
    assert partset is not None
    partset.user_id = None
    db.query(Favorite).filter(Favorite.partset_id == "pub1").delete()
    db.commit()

    claim_partset_for_user(db, partset, "alice")
    db.commit()

    db.refresh(partset)
    assert partset.user_id == "alice"


def test_update_favorite_owner_add_inserts_one_row_with_autoflush_off(db: Session) -> None:
    partset = db.query(Partset).filter(Partset.id == "pub1").first()
    assert partset is not None
    partset.user_id = None
    db.query(Favorite).filter(Favorite.partset_id == "pub1").delete()
    db.commit()

    update_favorite(db, "alice", "priv1", action="add")

    favorites = (
        db.query(Favorite)
        .filter(Favorite.partset_id == "pub1", Favorite.user_id == "alice")
        .all()
    )
    assert len(favorites) == 1
    assert favorites[0].admin is True
    db.refresh(partset)
    assert partset.user_id == "alice"


def test_update_favorite_public_add_does_not_claim(db: Session) -> None:
    partset = db.query(Partset).filter(Partset.id == "pub1").first()
    assert partset is not None
    partset.user_id = None
    db.query(Favorite).filter(Favorite.partset_id == "pub1").delete()
    db.commit()

    update_favorite(db, "bob", "pub1", action="add")

    db.refresh(partset)
    assert partset.user_id is None
    favorite = (
        db.query(Favorite)
        .filter(Favorite.partset_id == "pub1", Favorite.user_id == "bob")
        .one()
    )
    assert favorite.admin is False
