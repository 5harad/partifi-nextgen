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
_PAGE_ROT_RE = re.compile(r"Page rot:\s+(-?\d+)", re.IGNORECASE)


def infer_orientation_from_page_size(width_pt: float, height_pt: float) -> Orientation:
    """Classify orientation from native page dimensions in PDF points."""
    if width_pt > height_pt * PAGE_ASPECT_TOLERANCE:
        return "landscape"
    return "portrait"


def effective_page_size_pt(
    width_pt: float,
    height_pt: float,
    rotation_degrees: int,
) -> tuple[float, float]:
    """Return display width/height after applying PDF /Rotate (90° or 270° swaps axes)."""
    if rotation_degrees % 180 == 90:
        return height_pt, width_pt
    return width_pt, height_pt


def infer_orientation_from_pdf(pdf_path: Path) -> Orientation:
    """Infer score orientation from page 1 MediaBox and /Rotate via pdfinfo (~15ms)."""
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
    rot_match = _PAGE_ROT_RE.search(result.stdout)
    rotation = int(rot_match.group(1)) if rot_match else 0
    width_pt, height_pt = effective_page_size_pt(width_pt, height_pt, rotation)
    return infer_orientation_from_page_size(width_pt, height_pt)
