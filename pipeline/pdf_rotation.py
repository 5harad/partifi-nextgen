"""Read cardinal PDF page rotation metadata."""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_PAGE_SIZE_RE = re.compile(
    r"Page size:\s+(\d+(?:\.\d+)?)\s+x\s+(\d+(?:\.\d+)?)\s+pts",
    re.IGNORECASE,
)
_PAGE_ROT_RE = re.compile(r"Page rot:\s+(-?\d+)", re.IGNORECASE)
_CARDINAL_ROTATIONS = {0, 90, 180, 270}


def _pdfinfo(pdf_path: Path) -> str:
    result = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"pdfinfo failed for {pdf_path}: {result.stderr.strip()}")
    return result.stdout


def pdf_rotation_degrees(pdf_path: Path) -> int:
    """Return a single-page PDF's cardinal /Rotate metadata."""
    page_info = _pdfinfo(pdf_path)

    match = _PAGE_ROT_RE.search(page_info)
    rotation = int(match.group(1)) % 360 if match else 0
    if rotation not in _CARDINAL_ROTATIONS:
        logger.warning("Ignoring non-cardinal PDF /Rotate=%s for %s", rotation, pdf_path)
        return 0
    return rotation


def pdf_effective_page_size_points(pdf_path: Path) -> tuple[float, float]:
    """Return a PDF page's viewer-oriented dimensions in points."""
    page_info = _pdfinfo(pdf_path)
    size_match = _PAGE_SIZE_RE.search(page_info)
    if not size_match:
        raise ValueError(f"Could not read page size from {pdf_path}")
    width, height = (float(value) for value in size_match.groups())
    rotation_match = _PAGE_ROT_RE.search(page_info)
    rotation = int(rotation_match.group(1)) % 360 if rotation_match else 0
    if rotation % 180 == 90:
        return height, width
    return width, height
