"""Python 3 port of legacy pdf2png.py."""

from __future__ import annotations

import argparse
import glob
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

import db_conn
from pdf_repair import burst_score_pages, run_subprocess_with_repair
from pipeline.cut_segments import default_pool_size
from pipeline.parallel import map_in_parallel

logger = logging.getLogger(__name__)


def pdf2png(
    pdffile: str,
    outdir: str,
    partset_id: str | None,
    num_tasks: int,
    score_id: str | None = None,
) -> None:
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
        "-g2550x3300",
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
    lowres_im = im.resize((600, 776), Image.LANCZOS)
    lowres_file = os.path.join(outdir, "lowres", outfile)
    lowres_im.save(lowres_file)

    thumb_im = im.resize((100, 129), Image.LANCZOS)
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
) -> None:
    pdffile = os.path.abspath(pdffile)
    outdir = os.path.abspath(outdir)
    tempdir = tempfile.mkdtemp(dir="/tmp/partifi")
    origpath = os.getcwd()

    os.chdir(tempdir)
    burst_score_pages(pdffile, tempdir)
    os.chdir(origpath)

    for sub in ("highres", "lowres", "thumbs"):
        os.makedirs(os.path.join(outdir, sub), exist_ok=True)

    pdfpages = glob.glob(os.path.join(tempdir, "page*.pdf"))
    num_tasks = max(len(pdfpages), 1)
    params = [(pdfpage, outdir, partset_id, num_tasks, score_id) for pdfpage in pdfpages]

    workers = default_pool_size(len(params))
    map_in_parallel(pdf2png_star, params, workers=workers)

    shutil.rmtree(tempdir)


def convert_score(partset_id: str, pdf_path: Path, workdir: Path) -> None:
    db_conn.execute(
        "UPDATE partsets SET status = 'convert', convert_start = NOW(), convert_progress = 0 WHERE id = :id",
        {"id": partset_id},
    )
    par_pdf2png(str(pdf_path), str(workdir), partset_id)
    db_conn.execute(
        "UPDATE partsets SET convert_complete = NOW(), convert_progress = 100 WHERE id = :id",
        {"id": partset_id},
    )


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
