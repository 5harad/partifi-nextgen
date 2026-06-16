from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import Partset, Score
from app.services.partset_admin import update_partset_metadata


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    now = datetime.now(UTC)

    session.add(
        Score(
            id="score1",
            num_pages=1,
            import_complete=now,
            convert_complete=now,
            analysis_complete=now,
        )
    )
    session.add(
        Partset(
            id="pub1",
            private_id="priv1",
            score_id="score1",
            title="Old title",
            composer="Old composer",
            parts_ready=True,
            status="paste",
            import_complete=now,
            convert_complete=now,
            analysis_complete=now,
        )
    )
    session.commit()
    return session


@patch("app.services.partset_admin.get_local_cache")
def test_update_partset_metadata_invalidates_parts(mock_get_cache: Mock, db: Session) -> None:
    mock_cache = Mock()
    mock_get_cache.return_value = mock_cache
    partset = db.get(Partset, "pub1")
    assert partset is not None

    update_partset_metadata(
        db,
        partset,
        title="梁祝",
        composer="何占豪",
        publisher="",
    )

    db.expire_all()
    updated = db.get(Partset, "pub1")
    assert updated is not None
    assert updated.title == "梁祝"
    assert updated.composer == "何占豪"
    assert updated.parts_ready is False
    mock_cache.invalidate_parts.assert_called_once_with("pub1")
