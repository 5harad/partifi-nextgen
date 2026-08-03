"""Tests for race-safe imslp_info cache upsert."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models.tables import ImslpInfo
from app.services.imslp import _upsert_cache


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_upsert_cache_inserts_then_is_idempotent(db: Session) -> None:
    _upsert_cache(
        db,
        "549514",
        {
            "title": "Example Score",
            "composer": "Example Composer",
            "publisher": "Breitkopf",
            "copyright_raw": "Public Domain",
            "file_type": "PDF",
        },
        "https://imslp.org/wiki/Example#IMSLP549514",
    )
    _upsert_cache(
        db,
        "549514",
        {
            "title": "Example Score",
            "composer": "Example Composer",
            "publisher": "Breitkopf",
            "copyright_raw": "Public Domain",
            "file_type": "PDF",
        },
        "https://imslp.org/wiki/Example#IMSLP549514",
    )

    row = db.get(ImslpInfo, "549514")
    assert row is not None
    assert row.title == "Example Score"
    assert row.composer == "Example Composer"
    assert row.file_type == "PDF"


def test_upsert_cache_keeps_existing_when_incoming_empty(db: Session) -> None:
    _upsert_cache(
        db,
        "549514",
        {
            "title": "Example Score",
            "composer": "Example Composer",
            "publisher": "Breitkopf",
            "copyright_raw": "Public Domain",
            "file_type": "PDF",
        },
        "https://imslp.org/wiki/Example#IMSLP549514",
    )
    _upsert_cache(
        db,
        "549514",
        {"title": "", "composer": "", "publisher": "", "copyright_raw": "", "file_type": ""},
        "",
    )

    row = db.get(ImslpInfo, "549514")
    assert row is not None
    assert row.title == "Example Score"
    assert row.composer == "Example Composer"
    assert row.publisher == "Breitkopf"
    assert row.url == "https://imslp.org/wiki/Example#IMSLP549514"
    assert row.file_type == "PDF"
