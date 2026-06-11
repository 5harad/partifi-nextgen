from app.services.s3 import score_pdf_s3_key


def test_score_pdf_s3_key() -> None:
    assert score_pdf_s3_key("ecwrS") == "scores/ecwrS_score.pdf"
    assert score_pdf_s3_key("bfW65") == "scores/bfW65_score.pdf"
