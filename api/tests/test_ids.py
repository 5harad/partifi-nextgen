from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import Partset
from app.utils.ids import gen_partset_ids, gen_score_id, partset_id_in_use
from pipeline.ids import PARTIFI_ID_PATTERN


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    session.add(Partset(id="pubA", private_id="privB"))
    session.commit()
    return session


def test_partset_id_in_use_public_id(db: Session) -> None:
    assert partset_id_in_use(db, "pubA") is True


def test_partset_id_in_use_private_id(db: Session) -> None:
    assert partset_id_in_use(db, "privB") is True


def test_partset_id_in_use_unused(db: Session) -> None:
    assert partset_id_in_use(db, "free1") is False


@patch("app.utils.ids.rand_partifi_id")
def test_gen_partset_ids_rejects_cross_namespace(mock_rand_partifi_id, db: Session) -> None:
    mock_rand_partifi_id.side_effect = [
        "pubA",  # taken public id
        "privB",  # taken private id
        "newpy-bllic",
        "pubA",  # still taken
        "newpr-ivate",
    ]
    public_id, private_id = gen_partset_ids(db)
    assert public_id == "newpy-bllic"
    assert private_id == "newpr-ivate"
    assert public_id != private_id


@patch("app.utils.ids.rand_partifi_id")
def test_gen_partset_ids_rejects_same_value_for_both(mock_rand_partifi_id, db: Session) -> None:
    mock_rand_partifi_id.side_effect = ["same1-same1", "same1-same1", "priv1-vate1"]
    public_id, private_id = gen_partset_ids(db)
    assert public_id == "same1-same1"
    assert private_id == "priv1-vate1"


@patch("app.utils.ids.rand_partifi_id", return_value="abcde-fghij")
def test_gen_score_id_returns_new_format(mock_rand_partifi_id, db: Session) -> None:
    score_id = gen_score_id(db)
    assert score_id == "abcde-fghij"
    assert PARTIFI_ID_PATTERN.match(score_id)
