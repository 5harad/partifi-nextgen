"""Validate downloaded score PDFs before conversion."""

from __future__ import annotations

from pathlib import Path

PDF_MAGIC = b"%PDF"
MIN_PDF_BYTES = 1024


def validate_downloaded_pdf(path: Path, *, min_bytes: int = MIN_PDF_BYTES) -> None:
    size = path.stat().st_size
    if size < min_bytes:
        raise ValueError(f"Downloaded file too small ({size} bytes)")
    header = path.read_bytes()[: len(PDF_MAGIC)]
    if header != PDF_MAGIC:
        raise ValueError(f"Downloaded file is not a PDF (header {header!r})")
