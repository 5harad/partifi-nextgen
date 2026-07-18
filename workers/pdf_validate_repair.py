"""Validate score PDFs on disk, normalizing once through Ghostscript when needed."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from pdf_repair import normalize_pdf_for_convert
from pipeline.pdf_validate import PDF_CORRUPT_MESSAGE, validate_downloaded_pdf
from pipeline.pdfinfo_pages import assert_pdf_has_pages


def _validate_score_pdf(path: Path) -> None:
    validate_downloaded_pdf(path)
    assert_pdf_has_pages(path)


def ensure_valid_score_pdf(path: Path, workdir: Path) -> None:
    """Validate a score PDF, attempting one Ghostscript normalize before rejecting."""
    try:
        _validate_score_pdf(path)
        return
    except ValueError as first_exc:
        first_error = first_exc

    normalized = workdir / "score_normalized.pdf"
    repair_input = workdir / "score_repair_input.pdf"
    try:
        normalize_pdf_for_convert(
            str(path),
            str(normalized),
            repair_path=str(repair_input),
        )
        _validate_score_pdf(normalized)
    except (ValueError, subprocess.CalledProcessError):
        raise ValueError(PDF_CORRUPT_MESSAGE) from first_error
    shutil.move(str(normalized), str(path))
