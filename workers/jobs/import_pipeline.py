"""Import pipeline: convert PDF to PNGs and analyze segments."""

from __future__ import annotations

import glob
import logging
import shutil
from pathlib import Path

from find_segments import analyze_score
from pdf2png import convert_score
from s3_storage import download_file, upload_directory

logger = logging.getLogger("partifi.import_pipeline")


def run_import_pipeline(partset_id: str, score_id: str) -> None:
    workdir = Path(f"/tmp/partifi/{partset_id}")
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    pdf_path = workdir / "score.pdf"
    logger.info("Downloading score %s for partset %s", score_id, partset_id)
    download_file(f"scores/{score_id}/score.pdf", pdf_path)

    pages_dir = workdir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Converting PDF for partset %s", partset_id)
    convert_score(partset_id, pdf_path, pages_dir)

    logger.info("Uploading page images for score %s", score_id)
    upload_directory(pages_dir, f"scores/{score_id}")

    lowres_files = sorted(glob.glob(str(pages_dir / "lowres" / "*.png")))
    logger.info("Analyzing %d pages for partset %s", len(lowres_files), partset_id)
    analyze_score(partset_id, lowres_files)

    shutil.rmtree(workdir, ignore_errors=True)
    logger.info("Import pipeline complete for partset %s", partset_id)
