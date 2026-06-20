from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import Part, Partset, Score
from app.services.preview import save_layout


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
    for tag, spacing in (("violin", 0.1), ("cello", 0.2), ("bass", 0.3)):
        session.add(
            Part(
                partset_id="pub1",
                tag=tag,
                spacing=spacing,
                combined=False,
                file_name=f"{tag}.pdf",
            )
        )
    session.commit()
    return session


@patch("app.services.preview.get_local_cache")
def test_save_layout_updates_spacings_in_one_pass(mock_cache: Mock, db: Session) -> None:
    cache = Mock()
    mock_cache.return_value = cache
    partset = db.get(Partset, "pub1")
    assert partset is not None

    save_layout(
        db,
        partset,
        breaks={"violin": [1], "cello": []},
        spacings={"violin": 0.5, "cello": 0.6, "bass": 0.7},
    )

    db.expire_all()
    spacings = {
        row.tag: row.spacing
        for row in db.query(Part).filter(Part.partset_id == "pub1").order_by(Part.tag).all()
    }
    assert spacings == {"bass": 0.7, "cello": 0.6, "violin": 0.5}
    assert partset.parts_ready is False
    cache.invalidate_parts.assert_called_once_with("pub1")
    cache.invalidate_preview.assert_not_called()
