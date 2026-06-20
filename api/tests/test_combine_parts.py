from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import Part, Partset, Score
from app.services.preview import combine_parts


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
            parts_ready=True,
            status="paste",
            import_complete=now,
            convert_complete=now,
            analysis_complete=now,
        )
    )
    session.commit()
    return session


@patch("app.services.preview.get_local_cache")
def test_combine_parts_uses_short_filename(mock_cache: Mock, db: Session) -> None:
    mock_cache.return_value = Mock()
    partset = db.get(Partset, "pub1")
    assert partset is not None

    tag = " + ".join(str(i) for i in range(1, 11))
    combine_parts(db, partset, "add", tag)

    row = db.query(Part).filter(Part.partset_id == "pub1", Part.tag == tag).one()
    assert row.combined is True
    assert row.file_name.startswith("combined-")
    assert len(row.file_name) < 32


@patch("app.services.preview.get_local_cache")
def test_combine_parts_rejects_too_many_parts(mock_cache: Mock, db: Session) -> None:
    mock_cache.return_value = Mock()
    partset = db.get(Partset, "pub1")
    assert partset is not None

    tag = " + ".join(str(i) for i in range(1, 13))
    with pytest.raises(ValueError, match="Cannot combine more than"):
        combine_parts(db, partset, "add", tag)
