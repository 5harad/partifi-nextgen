from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from unittest.mock import MagicMock

from app.db import Base
from app.models import Part, Partset, Score
from app.services.downloads import resolve_part_cache_filename, safe_cached_part_path
from app.services.preview import get_parts_data
from app.utils.strings import tag_to_filename
from pipeline.part_filenames import combined_tag_to_filename

MEGA_COMBINED_TAG = " + ".join(str(i) for i in range(1, 53))


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    now = datetime.now(UTC)

    session.add(Score(id="score1", num_pages=1, import_complete=now, analysis_complete=now))
    session.add(
        Partset(
            id="ofBqc",
            private_id="m3WSh",
            score_id="score1",
            parts_ready=True,
            status="paste",
            import_complete=now,
            convert_complete=now,
            analysis_complete=now,
        )
    )
    session.add(
        Part(
            partset_id="ofBqc",
            tag=MEGA_COMBINED_TAG,
            spacing=0.1,
            combined=True,
            file_name=tag_to_filename(MEGA_COMBINED_TAG),
        )
    )
    session.commit()
    return session


def test_resolve_part_cache_filename_maps_legacy_long_combined_url(db: Session) -> None:
    long_name = tag_to_filename(MEGA_COMBINED_TAG)
    served = f"ofBqc_{long_name}"
    partset = db.get(Partset, "ofBqc")
    resolved = resolve_part_cache_filename(db, partset, served)
    assert resolved == f"ofBqc_{combined_tag_to_filename(MEGA_COMBINED_TAG)}"


def test_get_parts_data_emits_short_download_urls(db: Session) -> None:
    partset = db.get(Partset, "ofBqc")
    payload = get_parts_data(db, partset, mode="owner")
    short_name = combined_tag_to_filename(MEGA_COMBINED_TAG)
    assert payload["parts"][0]["file_name"] == short_name
    assert short_name in payload["parts"][0]["letter_url"]
    assert len(payload["parts"][0]["letter_url"]) < 120
    assert payload["imslp_id"] is None


def test_get_parts_data_includes_imslp_id(db: Session) -> None:
    partset = db.get(Partset, "ofBqc")
    partset.imslp_id = "282358"
    db.commit()

    payload = get_parts_data(db, partset, mode="owner")

    assert payload["imslp_id"] == "282358"


def test_get_parts_data_includes_partgen_error(db: Session) -> None:
    partset = db.get(Partset, "ofBqc")
    partset.parts_ready = False
    partset.error = "paste"
    partset.error_message = "Part page layout overflow"
    db.commit()

    payload = get_parts_data(db, partset, mode="owner")

    assert payload["parts_ready"] is False
    assert payload["error"] == "paste"
    assert payload["error_message"] == "Part page layout overflow"


def test_safe_cached_part_path_returns_none_for_overlong_filename() -> None:
    cache = MagicMock()
    cache.ensure_part_file.side_effect = OSError(36, "File name too long")
    assert safe_cached_part_path(cache, "ofBqc", "x" * 300 + ".pdf") is None


def test_resolve_part_cache_filename_rejects_unmatched_overlong_name(db: Session) -> None:
    partset = db.get(Partset, "ofBqc")
    served = f"ofBqc_{'x' * 220}.pdf"
    assert resolve_part_cache_filename(db, partset, served) is None
