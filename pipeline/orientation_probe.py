"""Fast score orientation inference from PDF page size."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from pipeline.orientation_detect import PAGE_ASPECT_TOLERANCE
from pipeline.page_dimensions import Orientation

_PAGE_SIZE_RE = re.compile(
    r"Page size:\s+(\d+(?:\.\d+)?)\s+x\s+(\d+(?:\.\d+)?)\s+pts",
    re.IGNORECASE,
)


def infer_orientation_from_page_size(width_pt: float, height_pt: float) -> Orientation:
    """Classify orientation from native page dimensions in PDF points."""
    if width_pt > height_pt * PAGE_ASPECT_TOLERANCE:
        return "landscape"
    return "portrait"


def infer_orientation_from_pdf(pdf_path: Path) -> Orientation:
    """Infer score orientation from page 1 MediaBox via pdfinfo (~15ms)."""
    result = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"pdfinfo failed for {pdf_path}: {result.stderr.strip()}")

    match = _PAGE_SIZE_RE.search(result.stdout)
    if not match:
        raise ValueError(f"Could not read page size from {pdf_path}")

    width_pt, height_pt = (float(value) for value in match.groups())
    return infer_orientation_from_page_size(width_pt, height_pt)
