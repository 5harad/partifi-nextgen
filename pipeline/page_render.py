"""Rasterize individual score PDF pages for orientation evaluation."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

WORKERS_ROOT = Path(__file__).resolve().parents[1] / "workers"
if str(WORKERS_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKERS_ROOT))

from pdf_repair import burst_score_pages, run_subprocess_with_repair

NATIVE_RENDER_DPI = 300
NATIVE_LOWRES_MAX_SIDE = 776
_BBOX_RE = re.compile(
    r"%%(?:HiRes)?BoundingBox:\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)"
)


def _page_size_points(page_pdf: Path) -> tuple[float, float]:
    """Return page width and height in PDF points via Ghostscript bbox."""
    result = subprocess.run(
        ["gs", "-q", "-dNOPAUSE", "-dBATCH", "-sDEVICE=bbox", str(page_pdf)],
        capture_output=True,
        text=True,
        check=False,
    )
    for line in (result.stdout + result.stderr).splitlines():
        match = _BBOX_RE.match(line.strip())
        if not match:
            continue
        x0, y0, x1, y1 = (float(value) for value in match.groups())
        width = abs(x1 - x0)
        height = abs(y1 - y0)
        if width > 0 and height > 0:
            return width, height
    raise ValueError(f"Could not read page size from {page_pdf}")


def _dpi_for_max_side(
    width_pt: float,
    height_pt: float,
    max_side: int = NATIVE_LOWRES_MAX_SIDE,
    cap_dpi: int = NATIVE_RENDER_DPI,
) -> int:
    """Pick a render DPI whose longest edge is at most max_side pixels."""
    max_pt = max(width_pt, height_pt)
    if max_pt <= 0:
        return cap_dpi
    dpi = int(max_side * 72 / max_pt)
    return max(1, min(cap_dpi, dpi))


def _gs_render_page_native(page_pdf: Path, out_png: Path, dpi: int = NATIVE_RENDER_DPI) -> None:
    """Render at the PDF page's natural size (no forced portrait/landscape canvas)."""
    out_png.parent.mkdir(parents=True, exist_ok=True)
    gs_cmd = [
        "gs",
        "-q",
        "-dNOPAUSE",
        "-dBATCH",
        "-sDEVICE=pnggray",
        "-dDOINTERPOLATE",
        "-dUseCropBox",
        f"-r{dpi}",
        f"-sOutputFile={out_png}",
        str(page_pdf),
    ]
    repair_path = str(page_pdf) + ".repaired.pdf"
    run_subprocess_with_repair(
        gs_cmd,
        input_pdf=str(page_pdf),
        repair_path=repair_path,
        label="Native page render",
    )
    if os.path.exists(repair_path):
        os.remove(repair_path)


def _resize_native_lowres(im: Image.Image, max_side: int = NATIVE_LOWRES_MAX_SIDE) -> Image.Image:
    width, height = im.size
    scale = max_side / max(width, height)
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return im.resize(new_size, Image.LANCZOS)


def burst_pdf(pdf_path: Path, workdir: Path | None = None) -> tuple[Path, list[Path]]:
    """Burst a score PDF into per-page files; return workdir and sorted page PDF paths."""
    cleanup = workdir is None
    if workdir is None:
        workdir = Path(tempfile.mkdtemp(prefix="partifi-orient-"))
    else:
        workdir.mkdir(parents=True, exist_ok=True)

    burst_score_pages(str(pdf_path), str(workdir))
    page_pdfs = sorted(workdir.glob("page-*.pdf"), key=lambda p: int(p.stem.split("-")[1]))
    if not page_pdfs:
        if cleanup:
            import shutil

            shutil.rmtree(workdir, ignore_errors=True)
        raise ValueError(f"No pages found after bursting {pdf_path}")
    return workdir, page_pdfs


def render_page_native_lowres(page_pdf: Path, out_dir: Path) -> Image.Image:
    """Render one page at native PDF dimensions, scaled for analysis."""
    lowres_png = out_dir / f"{page_pdf.stem}-native-lowres.png"
    width_pt, height_pt = _page_size_points(page_pdf)
    dpi = _dpi_for_max_side(width_pt, height_pt)
    _gs_render_page_native(page_pdf, lowres_png, dpi=dpi)
    with Image.open(lowres_png) as lowres_im:
        result = _resize_native_lowres(lowres_im)
    result.save(lowres_png)
    return result
