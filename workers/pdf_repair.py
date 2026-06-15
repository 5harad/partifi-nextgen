"""Ghostscript helpers to normalize and repair PDFs before convert."""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)

_GS_QUIET = ["gs", "-q", "-dNOPAUSE", "-dBATCH"]
_GS_PDFWRITE = [*_GS_QUIET, "-sDEVICE=pdfwrite", "-dPDFSETTINGS=/prepress"]


def gs_pdfwrite(input_pdf: str, output_pdf: str) -> None:
    subprocess.check_call([*_GS_PDFWRITE, f"-sOutputFile={output_pdf}", input_pdf])


def repair_pdf(input_pdf: str, output_pdf: str) -> None:
    """Re-serialize a PDF through Ghostscript to fix common stream/xref defects."""
    gs_pdfwrite(input_pdf, output_pdf)


def normalize_pdf_for_convert(input_pdf: str, output_pdf: str, *, repair_path: str) -> None:
    """Normalize a score PDF for pdftk/GS convert, repairing once on failure."""
    try:
        gs_pdfwrite(input_pdf, output_pdf)
    except subprocess.CalledProcessError as exc:
        logger.warning("PDF normalize failed for %s, attempting repair: %s", input_pdf, exc)
        repair_pdf(input_pdf, repair_path)
        gs_pdfwrite(repair_path, output_pdf)


def run_subprocess_with_repair(
    cmd: list[str],
    *,
    input_pdf: str,
    repair_path: str,
    label: str,
) -> None:
    """Run a subprocess on a PDF; repair the input and retry once on failure."""
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as exc:
        logger.warning("%s failed for %s, attempting repair: %s", label, input_pdf, exc)
        repair_pdf(input_pdf, repair_path)
        retry_cmd = list(cmd)
        input_idx = retry_cmd.index(input_pdf)
        retry_cmd[input_idx] = repair_path
        subprocess.check_call(retry_cmd)
