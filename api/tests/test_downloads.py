from app.models import Partset
from app.services.downloads import (
    part_file_url,
    score_pdf_url_for_access,
    score_pdf_url_for_owner,
    score_pdf_url_for_partset,
    score_pdf_url_for_score,
)


def test_score_pdf_url_for_score() -> None:
    assert score_pdf_url_for_score("ecwrS") == "/api/v1/scores/ecwrS/score.pdf"


def test_score_pdf_url_for_access() -> None:
    assert score_pdf_url_for_access("lkP8w") == "/api/v1/access/lkP8w/score-pdf"


def test_score_pdf_url_for_owner() -> None:
    assert score_pdf_url_for_owner("s3VK6") == "/api/v1/partsets/s3VK6/score-pdf"


def test_part_file_urls() -> None:
    partset = Partset(id="pub01", private_id="priv1")
    assert (
        part_file_url(partset, "pub01_flute.pdf", mode="owner")
        == "/api/v1/partsets/priv1/part-file/pub01_flute.pdf"
    )
    assert (
        part_file_url(partset, "pub01_flute.pdf", mode="public")
        == "/api/v1/access/pub01/part-file/pub01_flute.pdf"
    )


def test_score_pdf_url_for_partset_modes() -> None:
    partset = Partset(id="pub01", private_id="priv1", score_id="sc01")
    assert score_pdf_url_for_partset(partset, mode="owner") == "/api/v1/partsets/priv1/score-pdf"
    assert score_pdf_url_for_partset(partset, mode="public") == "/api/v1/access/pub01/score-pdf"
    assert score_pdf_url_for_partset(Partset(id="pub02", score_id=None)) is None
