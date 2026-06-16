from unittest.mock import MagicMock

import pytest

from app.services.partsets import create_partset_from_score


def test_create_partset_from_score_rejects_missing_score() -> None:
    db = MagicMock()
    db.get.return_value = None
    with pytest.raises(ValueError, match="Score not found"):
        create_partset_from_score(
            db,
            score_id="abc12",
            title="Title",
            composer="Composer",
            publisher="",
            copyright="before 1923",
        )


def test_create_partset_from_score_rejects_unavailable_pdf() -> None:
    score = MagicMock()
    score.s3 = False
    score.file_size = 0
    db = MagicMock()
    db.get.return_value = score
    with pytest.raises(ValueError, match="Score PDF is not available"):
        create_partset_from_score(
            db,
            score_id="abc12",
            title="Title",
            composer="Composer",
            publisher="",
            copyright="before 1923",
        )
