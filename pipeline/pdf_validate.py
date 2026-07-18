"""Validate downloaded score PDFs before conversion."""

from __future__ import annotations

from pathlib import Path

PDF_MAGIC = b"%PDF"
MIN_PDF_BYTES = 1024
TAIL_SCAN_BYTES = 4096
FULL_READ_MAX_BYTES = 10_000_000
PDF_CORRUPT_MESSAGE = "This score PDF is corrupt or incomplete."


def _final_eof_offset(data: bytes) -> int | None:
    """Return the start offset of the last %%EOF, if any."""
    pos = data.rfind(b"%%EOF")
    return None if pos < 0 else pos


def _pdf_structure_ok(data: bytes) -> bool:
    """Require the final %%EOF near the end (not an early linearized marker only)."""
    eof_pos = _final_eof_offset(data)
    if eof_pos is None:
        return False
    # Truncated linearized PDFs often keep an early %%EOF while the real trailer is missing.
    if len(data) - eof_pos > TAIL_SCAN_BYTES:
        return False

    trailer_window = data[max(0, eof_pos - TAIL_SCAN_BYTES) :]
    if b"startxref" in trailer_window.lower():
        return True
    if b"/xref" in trailer_window.lower():
        return True
    # Final %%EOF is present; allow startxref elsewhere (rare trailer layouts).
    return b"startxref" in data.lower()


def validate_pdf_bytes(data: bytes, *, min_bytes: int = MIN_PDF_BYTES) -> None:
    if len(data) < min_bytes:
        raise ValueError(f"Downloaded file too small ({len(data)} bytes)")
    if not data.startswith(PDF_MAGIC):
        raise ValueError(f"Downloaded file is not a PDF (header {data[:8]!r})")
    if not _pdf_structure_ok(data):
        raise ValueError(PDF_CORRUPT_MESSAGE)


def validate_downloaded_pdf(path: Path, *, min_bytes: int = MIN_PDF_BYTES) -> None:
    size = path.stat().st_size
    if size < min_bytes:
        raise ValueError(f"Downloaded file too small ({size} bytes)")
    if size <= FULL_READ_MAX_BYTES:
        validate_pdf_bytes(path.read_bytes(), min_bytes=min_bytes)
        return

    with path.open("rb") as handle:
        header = handle.read(len(PDF_MAGIC))
        if header != PDF_MAGIC:
            raise ValueError(f"Downloaded file is not a PDF (header {header!r})")
        handle.seek(-TAIL_SCAN_BYTES, 2)
        tail = handle.read()

    if b"%%EOF" not in tail:
        raise ValueError(PDF_CORRUPT_MESSAGE)

    if b"startxref" in tail.lower() or b"/xref" in tail.lower():
        return

    if b"startxref" in path.read_bytes().lower():
        return

    raise ValueError(PDF_CORRUPT_MESSAGE)
