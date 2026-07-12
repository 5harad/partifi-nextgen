"""Python 3 port of legacy pdf2png.py."""

from __future__ import annotations

import argparse
import glob
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path

from PIL import Image

import db_conn
from pdf_repair import burst_score_pages, run_subprocess_with_repair
from pipeline.cut_segments import default_pool_size
from pipeline.partset_orientation import layout_orientation
from pipeline.orientation_detect import detect_orientation_from_images
from pipeline.page_dimensions import Orientation, get_dimensions
from pipeline.page_render import render_page_native_lowres
from pipeline.parallel import map_in_parallel

logger = logging.getLogger(__name__)

_PAGE_NUM_RE = re.compile(r"page-?(\d+)")


def _page_number(path: str) -> int:
    match = _PAGE_NUM_RE.search(os.path.basename(path))
    if not match:
        return 0
    return int(match.group(1))


def _detect_orientation_from_burst(tempdir: str) -> Orientation:
    page_pdfs = sorted(glob.glob(os.path.join(tempdir, "page*.pdf")), key=_page_number)
    if not page_pdfs:
        return "portrait"
    detect_dir = Path(tempdir) / "orient-detect"
    native_im = render_page_native_lowres(Path(page_pdfs[0]), detect_dir)
    detection = detect_orientation_from_images([(1, native_im)])
    logger.info(
        "Detected score orientation=%s (confidence=%.3f, uncertain=%s)",
        detection.orientation,
        detection.confidence,
        detection.uncertain,
    )
    return detection.orientation


def pdf2png(
    pdffile: str,
    outdir: str,
    partset_id: str | None,
    num_tasks: int,
    score_id: str | None = None,
    orientation: Orientation = "portrait",
    rotation_degrees: int = 0,
) -> None:
    dims = get_dimensions(orientation)
    outfile = os.path.basename(pdffile).rsplit(".", 1)[0] + ".png"
    highres_file = os.path.join(outdir, "highres", outfile)
    gs_cmd = [
        "gs",
        "-q",
        "-dNOPAUSE",
        "-dBATCH",
        "-sDEVICE=pnggray",
        "-dDOINTERPOLATE",
        "-dUseCropBox",
        "-dPDFFitPage",
        f"-g{dims.gs_canvas}",
        f"-sOutputFile={highres_file}",
        pdffile,
    ]
    repair_path = pdffile + ".repaired.pdf"
    run_subprocess_with_repair(
        gs_cmd,
        input_pdf=pdffile,
        repair_path=repair_path,
        label="Page PNG convert",
    )
    if os.path.exists(repair_path):
        os.remove(repair_path)

    im = Image.open(highres_file)
    if rotation_degrees:
        im = im.rotate(rotation_degrees, expand=True, fillcolor=255)
        im.save(highres_file)
        dims = get_dimensions(layout_orientation(orientation, rotation_degrees))
    lowres_im = im.resize(dims.lowres_size, Image.LANCZOS)
    lowres_file = os.path.join(outdir, "lowres", outfile)
    lowres_im.save(lowres_file)

    thumb_im = im.resize(dims.thumb_size, Image.LANCZOS)
    thumb_file = os.path.join(outdir, "thumbs", outfile)
    thumb_im.save(thumb_file)

    progress = 100.0 / num_tasks
    if partset_id:
        db_conn.execute(
            "UPDATE partsets SET convert_progress = convert_progress + :progress WHERE id = :id",
            {"progress": progress, "id": partset_id},
        )
    elif score_id:
        from warm_progress import add_warm_progress

        add_warm_progress(score_id, progress)


def pdf2png_star(args):
    return pdf2png(*args)


def par_pdf2png(
    pdffile: str,
    outdir: str,
    partset_id: str | None,
    *,
    score_id: str | None = None,
    orientation: Orientation | None = None,
    rotation_degrees: int = 0,
) -> Orientation:
    pdffile = os.path.abspath(pdffile)
    outdir = os.path.abspath(outdir)
    tempdir = tempfile.mkdtemp(dir="/tmp/partifi")
    origpath = os.getcwd()

    os.chdir(tempdir)
    burst_score_pages(pdffile, tempdir)
    os.chdir(origpath)

    if orientation is None:
        orientation = _detect_orientation_from_burst(tempdir)

    for sub in ("highres", "lowres", "thumbs"):
        os.makedirs(os.path.join(outdir, sub), exist_ok=True)

    pdfpages = sorted(glob.glob(os.path.join(tempdir, "page*.pdf")), key=_page_number)
    num_tasks = max(len(pdfpages), 1)
    params = [
        (pdfpage, outdir, partset_id, num_tasks, score_id, orientation, rotation_degrees)
        for pdfpage in pdfpages
    ]

    workers = default_pool_size(len(params))
    map_in_parallel(pdf2png_star, params, workers=workers)

    shutil.rmtree(tempdir)
    return orientation


def convert_score(
    partset_id: str,
    pdf_path: Path,
    workdir: Path,
    *,
    orientation: Orientation | None = None,
) -> Orientation:
    db_conn.execute(
        "UPDATE partsets SET status = 'convert', convert_start = NOW(), convert_progress = 0 WHERE id = :id",
        {"id": partset_id},
    )
    orientation = par_pdf2png(
        str(pdf_path),
        str(workdir),
        partset_id,
        orientation=orientation,
    )
    db_conn.execute(
        "UPDATE partsets SET convert_complete = NOW(), convert_progress = 100 WHERE id = :id",
        {"id": partset_id},
    )
    return orientation


def main() -> None:
    parser = argparse.ArgumentParser(description="Parallel conversion of a PDF to PNG")
    parser.add_argument("inputpdf")
    parser.add_argument("outdir")
    parser.add_argument("--update-db", metavar="partset_id", dest="partset_id", default=None)
    args = parser.parse_args()
    convert_score(args.partset_id, Path(args.inputpdf), Path(args.outdir)) if args.partset_id else par_pdf2png(
        args.inputpdf, args.outdir, None
    )


if __name__ == "__main__":
    main()
