from app.models import Partset
from app.services.downloads import (
    part_file_name_from_download_filename,
    part_file_url,
    score_pdf_url_for_access,
    score_pdf_url_for_owner,
    score_pdf_url_for_partset,
    score_pdf_url_for_score,
)


def test_score_pdf_url_for_score() -> None:
    assert score_pdf_url_for_score("ecwrS") == "/api/v1/scores/ecwrS/score.pdf"


def test_score_pdf_url_for_access() -> None:
    assert score_pdf_url_for_access("lkP8w") == "/api/v1/access/lkP8w/score.pdf"


def test_score_pdf_url_for_owner() -> None:
    assert score_pdf_url_for_owner("s3VK6") == "/api/v1/partsets/s3VK6/score.pdf"


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
    assert score_pdf_url_for_partset(partset, mode="owner") == "/api/v1/partsets/priv1/score.pdf"
    assert score_pdf_url_for_partset(partset, mode="public") == "/api/v1/access/pub01/score.pdf"
    assert score_pdf_url_for_partset(Partset(id="pub02", score_id=None)) is None


def test_part_file_urls_encode_plus() -> None:
    partset = Partset(id="pub01", private_id="priv1")
    combined = "pub01_violin_+_cello.pdf"
    assert (
        part_file_url(partset, combined, mode="owner")
        == "/api/v1/partsets/priv1/part-file/pub01_violin_%2B_cello.pdf"
    )
    assert (
        part_file_url(partset, combined, mode="public")
        == "/api/v1/access/pub01/part-file/pub01_violin_%2B_cello.pdf"
    )


def test_part_file_name_from_download_filename() -> None:
    assert part_file_name_from_download_filename("pub01", "pub01_flute.pdf") == ("flute.pdf", False)
    assert part_file_name_from_download_filename("pub01", "pub01_a4_flute.pdf") == (
        "flute.pdf",
        True,
    )
    assert part_file_name_from_download_filename("pub01", "pub01_violin_+_cello.pdf") == (
        "violin_+_cello.pdf",
        False,
    )
    assert part_file_name_from_download_filename("pub01", "other_flute.pdf") is None
    assert part_file_name_from_download_filename("pub01", "pub01_flute.txt") is None
