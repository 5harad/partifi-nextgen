"""Require pdfinfo to report a usable page count."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from pipeline.pdf_validate import PDF_CORRUPT_MESSAGE

_PAGES_RE = re.compile(r"Pages:\s+(\d+)", re.IGNORECASE)


def assert_pdf_has_pages(pdf_path: Path, *, min_pages: int = 1) -> int:
    """Raise PDF_CORRUPT_MESSAGE when pdfinfo fails or reports too few pages."""
    result = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(PDF_CORRUPT_MESSAGE)

    match = _PAGES_RE.search(result.stdout)
    if not match:
        raise ValueError(PDF_CORRUPT_MESSAGE)

    pages = int(match.group(1))
    if pages < min_pages:
        raise ValueError(PDF_CORRUPT_MESSAGE)
    return pages
