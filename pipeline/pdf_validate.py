"""Validate downloaded score PDFs before conversion."""

from __future__ import annotations

from pathlib import Path

PDF_MAGIC = b"%PDF"
MIN_PDF_BYTES = 1024
TAIL_SCAN_BYTES = 4096
# For large files, inspect this many trailing bytes so a final trailer is visible
# even with a modest amount of post-%%EOF padding.
LARGE_FILE_TAIL_BYTES = 256_000
FULL_READ_MAX_BYTES = 10_000_000
PDF_CORRUPT_MESSAGE = "This score PDF is corrupt or incomplete."
_EOF_MARKER = b"%%EOF"


def _trailing_indicates_incomplete_pdf(after: bytes) -> bool:
    """True when bytes after %%EOF look like more PDF body (truncated linearized)."""
    if not after:
        return False
    # Readers ignore ordinary whitespace / NUL padding after the trailer.
    if not after.strip(b" \t\r\n\x00"):
        return False
    lower = after.lower()
    return (
        b"endobj" in lower
        or b"stream" in lower
        or b"startxref" in lower
        or b"%%eof" in lower
    )


def _pdf_structure_ok(data: bytes) -> bool:
    """Require a real trailer at the last %%EOF; reject truncated linearized bodies."""
    eof_pos = data.rfind(_EOF_MARKER)
    if eof_pos < 0:
        return False

    trailer_window = data[max(0, eof_pos - TAIL_SCAN_BYTES) : eof_pos]
    # Require startxref next to this %%EOF (do not accept an earlier linearized one alone).
    if b"startxref" not in trailer_window.lower():
        return False

    after = data[eof_pos + len(_EOF_MARKER) :]
    if _trailing_indicates_incomplete_pdf(after):
        return False
    return True


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

    tail = _read_suffix_including_eof(path, size)
    # Tail is a suffix of the real file, so post-%%EOF checks still apply.
    if not _pdf_structure_ok(tail):
        raise ValueError(PDF_CORRUPT_MESSAGE)


def _read_suffix_including_eof(path: Path, size: int) -> bytes:
    """Load a file suffix that includes the last %%EOF when padding follows it."""
    with path.open("rb") as handle:
        header = handle.read(len(PDF_MAGIC))
        if header != PDF_MAGIC:
            raise ValueError(f"Downloaded file is not a PDF (header {header!r})")

        for window in (LARGE_FILE_TAIL_BYTES, 8_000_000):
            nbytes = min(size, window)
            handle.seek(-nbytes, 2)
            tail = handle.read()
            if _EOF_MARKER in tail:
                return tail

        handle.seek(0)
        return handle.read()
