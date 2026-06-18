import subprocess
from unittest.mock import patch

import pytest

from pdf_repair import normalize_pdf_for_convert, run_subprocess_with_repair


def test_normalize_pdf_for_convert_succeeds_without_repair() -> None:
    with patch("pdf_repair.gs_pdfwrite") as write:
        normalize_pdf_for_convert("in.pdf", "out.pdf", repair_path="repair.pdf")
    write.assert_called_once_with("in.pdf", "out.pdf")


def test_normalize_pdf_for_convert_repairs_on_failure() -> None:
    with patch("pdf_repair.gs_pdfwrite") as write, patch("pdf_repair.repair_pdf") as repair:
        write.side_effect = [subprocess.CalledProcessError(1, "gs"), None]
        normalize_pdf_for_convert("in.pdf", "out.pdf", repair_path="repair.pdf")
    repair.assert_called_once_with("in.pdf", "repair.pdf")
    assert write.call_args_list[-1].args == ("repair.pdf", "out.pdf")


def test_run_subprocess_with_repair_retries_after_repair() -> None:
    cmd = ["gs", "-sOutputFile=out.png", "page.pdf"]
    with (
        patch("pdf_repair.subprocess.check_call") as check,
        patch("pdf_repair.repair_pdf") as repair,
    ):
        check.side_effect = [subprocess.CalledProcessError(1, "gs"), None]
        run_subprocess_with_repair(
            cmd,
            input_pdf="page.pdf",
            repair_path="page.repaired.pdf",
            label="Page PNG convert",
        )
    repair.assert_called_once_with("page.pdf", "page.repaired.pdf")
    assert check.call_args_list[-1].args[0][-1] == "page.repaired.pdf"


def test_burst_score_pages_uses_original_when_pdftk_succeeds() -> None:
    from pdf_repair import burst_score_pages

    with (
        patch("pdf_repair._pdftk_burst") as burst,
        patch("pdf_repair.glob.glob", side_effect=[[], ["/tmp/partifi/x/page-1.pdf"]]),
        patch("pdf_repair.normalize_pdf_for_convert") as normalize,
    ):
        burst_score_pages("/tmp/in.pdf", "/tmp/partifi/x")

    burst.assert_called_once_with("/tmp/in.pdf", "/tmp/partifi/x/page-%d.pdf")
    normalize.assert_not_called()


def test_burst_score_pages_normalizes_when_pdftk_fails() -> None:
    from pdf_repair import burst_score_pages

    with (
        patch("pdf_repair._pdftk_burst", side_effect=subprocess.CalledProcessError(1, "pdftk")),
        patch("pdf_repair.glob.glob", side_effect=[[], [], ["/tmp/partifi/x/page-1.pdf"]]),
        patch("pdf_repair.normalize_pdf_for_convert") as normalize,
        patch("pdf_repair.run_subprocess_with_repair") as burst_repair,
    ):
        burst_score_pages("/tmp/in.pdf", "/tmp/partifi/x")

    normalize.assert_called_once_with(
        "/tmp/in.pdf",
        "/tmp/partifi/x/score.pdf",
        repair_path="/tmp/partifi/x/score_repair_input.pdf",
    )
    burst_repair.assert_called_once()


def test_burst_score_pages_raises_when_no_pages_produced() -> None:
    from pdf_repair import burst_score_pages

    with (
        patch("pdf_repair._pdftk_burst", side_effect=subprocess.CalledProcessError(1, "pdftk")),
        patch("pdf_repair.glob.glob", return_value=[]),
        patch("pdf_repair.normalize_pdf_for_convert"),
        patch("pdf_repair.run_subprocess_with_repair"),
    ):
        with pytest.raises(ValueError, match="corrupt or incomplete"):
            burst_score_pages("/tmp/in.pdf", "/tmp/partifi/x")
