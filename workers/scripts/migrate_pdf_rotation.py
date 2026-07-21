"""Migrate viewer-validated legacy partsets from manual to PDF metadata rotation.

Run this only in the worker environment. The default mode is read-only:

    python scripts/migrate_pdf_rotation.py

After reviewing its report and a viewer-oriented preview, pass both --apply
and --viewer-validated to rebuild the two confirmed partsets.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent
for root in (APP_ROOT, REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

import db_conn
from jobs.gen_parts import run_gen_parts
from local_cache import get_local_cache
from pdf2png import par_pdf2png
from pdf_repair import burst_score_pages
from pipeline.pdf_rotation import pdf_rotation_degrees
from s3_storage import download_file, score_pdf_s3_key

CONFIRMED_PARTSET_ROTATIONS = {
    "jigmi-xqpek": 270,
    "dliol-bejej": 270,
}


def _partset_row(partset_id: str):
    row = db_conn.fetchone(
        """
        SELECT id, private_id, score_id, rotation_degrees, orientation_override,
               status, parts_ready, last_job_id
        FROM partsets
        WHERE id = :partset_id
        """,
        {"partset_id": partset_id},
    )
    if not row:
        raise RuntimeError(f"Partset {partset_id} was not found")
    if not row.score_id:
        raise RuntimeError(f"Partset {partset_id} has no score")
    return row


def _score_orientation(score_id: str) -> str:
    row = db_conn.fetchone("SELECT orientation FROM scores WHERE id = :id", {"id": score_id})
    if not row or row.orientation not in ("portrait", "landscape"):
        raise RuntimeError(f"Score {score_id} has no supported orientation")
    return str(row.orientation)


def _download_score_pdf(score_id: str, workdir: Path) -> Path:
    """Fetch the source into migration scratch space without touching shared cache."""
    score_pdf = workdir / "score.pdf"
    download_file(score_pdf_s3_key(score_id), score_pdf)
    return score_pdf


def _source_rotations(score_pdf: Path, workdir: Path) -> list[int]:
    burst_dir = workdir / "burst"
    burst_dir.mkdir()
    burst_score_pages(str(score_pdf), str(burst_dir))
    pages = sorted(burst_dir.glob("page-*.pdf"), key=lambda path: int(path.stem.split("-")[1]))
    return [pdf_rotation_degrees(page) for page in pages]


def _render_normalized_score(score_pdf: Path, workdir: Path, orientation: str) -> Path:
    pages_dir = workdir / "pages"
    par_pdf2png(str(score_pdf), str(pages_dir), None, orientation=orientation)  # type: ignore[arg-type]
    return pages_dir


def _apply(row, rendered_pages: Path) -> None:
    cache = get_local_cache()
    cache.invalidate_score_pages(row.score_id)
    cache.copy_pages_tree(row.score_id, rendered_pages)
    cache.invalidate_partset_pages(row.id)
    cache.invalidate_preview(row.id)
    cache.invalidate_parts(row.id)
    db_conn.execute(
        """
        UPDATE partsets
        SET rotation_degrees = 0,
            parts_ready = 0,
            status = 'analysis',
            cut_start = NULL,
            cut_complete = NULL,
            cut_progress = 0,
            paste_start = NULL,
            paste_complete = NULL,
            paste_progress = 0,
            last_job_id = NULL
        WHERE id = :id
        """,
        {"id": row.id},
    )
    run_gen_parts(row.id, job_id="pdf-rotation-migration")


def _migrate(partset_id: str, *, apply: bool) -> None:
    expected_rotation = CONFIRMED_PARTSET_ROTATIONS[partset_id]
    row = _partset_row(partset_id)
    if int(row.rotation_degrees or 0) != 180:
        raise RuntimeError(f"Partset {partset_id} is not a confirmed 180° manual rotation")
    if row.last_job_id or (not row.parts_ready and row.status in ("cut", "paste")):
        raise RuntimeError(f"Partset {partset_id} has an active generation job")

    workdir = Path(tempfile.mkdtemp(prefix=f"partifi-rotation-{row.id}-"))
    try:
        score_pdf = _download_score_pdf(row.score_id, workdir)
        rotations = _source_rotations(score_pdf, workdir)
        if not rotations or any(rotation != expected_rotation for rotation in rotations):
            raise RuntimeError(
                f"Score {row.score_id} does not have uniform /Rotate {expected_rotation} metadata: {rotations}"
            )

        orientation = _score_orientation(row.score_id)
        rendered_pages = _render_normalized_score(score_pdf, workdir, orientation)
        print(
            f"{partset_id}: private_id={row.private_id} score={row.score_id} "
            f"rotations={rotations} orientation_override={row.orientation_override} apply={apply}"
        )
        if apply:
            _apply(row, rendered_pages)
            print(f"{partset_id}: migrated and parts regenerated")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate confirmed manual PDF rotations")
    parser.add_argument("--apply", action="store_true", help="Apply the verified migration")
    parser.add_argument(
        "--viewer-validated",
        action="store_true",
        help="Confirm that the prospective page renders were visually compared with the PDF viewer",
    )
    parser.add_argument(
        "--partset",
        action="append",
        choices=CONFIRMED_PARTSET_ROTATIONS,
        help="Migrate one confirmed partset (defaults to both)",
    )
    args = parser.parse_args()
    if args.apply and not args.viewer_validated:
        parser.error("--apply requires --viewer-validated")
    for partset_id in args.partset or CONFIRMED_PARTSET_ROTATIONS:
        _migrate(partset_id, apply=args.apply)


if __name__ == "__main__":
    main()
