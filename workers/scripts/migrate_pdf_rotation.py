"""Migrate viewer-validated legacy partsets from manual to PDF metadata rotation.

Run this only in the worker environment. The default mode is read-only:

    python scripts/migrate_pdf_rotation.py --partset <partset-id>

After reviewing its report and a viewer-oriented preview, an approved
single-partset candidate may be migrated with --apply, --viewer-validated,
and the source PDF rotation reported by the dry run.
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

# Add a partset only after its prospective render and stored segment geometry
# have been reviewed. Shared-score groups remain blocked by _migrate.
APPROVED_PARTSET_IDS = {
    "dsbmc-wmhka",
    "qbccm-ogcoz",
    "blbfw-frboc",
    "efibz-itxmb",
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


def _score_sibling_partsets(score_id: str, partset_id: str) -> list[str]:
    rows = db_conn.fetchall(
        "SELECT id FROM partsets WHERE score_id = :score_id AND id != :partset_id",
        {"score_id": score_id, "partset_id": partset_id},
    )
    return [str(row.id) for row in rows]


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


def _apply(row, rendered_pages: Path, score_orientation: str) -> None:
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
            orientation_override = CASE
                WHEN orientation_override = :score_orientation THEN NULL
                ELSE orientation_override
            END,
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
        {"id": row.id, "score_orientation": score_orientation},
    )
    run_gen_parts(row.id, job_id="pdf-rotation-migration")


def _migrate(partset_id: str, *, apply: bool, expected_rotation: int | None) -> None:
    row = _partset_row(partset_id)
    if not int(row.rotation_degrees or 0):
        raise RuntimeError(f"Partset {partset_id} has no manual rotation to migrate")
    if row.last_job_id or (not row.parts_ready and row.status in ("cut", "paste")):
        raise RuntimeError(f"Partset {partset_id} has an active generation job")

    workdir = Path(tempfile.mkdtemp(prefix=f"partifi-rotation-{row.id}-"))
    try:
        score_pdf = _download_score_pdf(row.score_id, workdir)
        rotations = _source_rotations(score_pdf, workdir)
        if not rotations or len(set(rotations)) != 1:
            raise RuntimeError(f"Score {row.score_id} does not have uniform PDF rotation metadata: {rotations}")
        actual_rotation = rotations[0]
        if expected_rotation is not None and actual_rotation != expected_rotation:
            raise RuntimeError(
                f"Score {row.score_id} has /Rotate {actual_rotation}, not expected {expected_rotation}"
            )

        orientation = _score_orientation(row.score_id)
        rendered_pages = _render_normalized_score(score_pdf, workdir, orientation)
        siblings = _score_sibling_partsets(row.score_id, row.id)
        print(
            f"{partset_id}: private_id={row.private_id} score={row.score_id} "
            f"rotation={actual_rotation} orientation_override={row.orientation_override} "
            f"siblings={siblings} apply={apply}"
        )
        if apply:
            if siblings:
                raise RuntimeError(
                    f"Score {row.score_id} is shared with partsets {siblings}; "
                    "use a score-group migration instead"
                )
            _apply(row, rendered_pages, orientation)
            print(f"{partset_id}: migrated and parts regenerated")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate confirmed manual PDF rotations")
    parser.add_argument("--apply", action="store_true", help="Apply an approved verified migration")
    parser.add_argument(
        "--viewer-validated",
        action="store_true",
        help="Confirm that the prospective page renders were visually compared with the PDF viewer",
    )
    parser.add_argument(
        "--partset",
        action="append",
        required=True,
        help="Internal partset ID to inspect or migrate",
    )
    parser.add_argument(
        "--expected-rotation",
        type=int,
        choices=(0, 90, 180, 270),
        help="Source PDF /Rotate value reported by a successful dry run; required with --apply",
    )
    args = parser.parse_args()
    if args.apply and not args.viewer_validated:
        parser.error("--apply requires --viewer-validated")
    if args.apply:
        if args.expected_rotation is None:
            parser.error("--apply requires --expected-rotation")
        unapproved = [partset_id for partset_id in args.partset if partset_id not in APPROVED_PARTSET_IDS]
        if unapproved:
            parser.error(f"--apply requires approved candidates: {', '.join(unapproved)}")
    for partset_id in args.partset:
        _migrate(partset_id, apply=args.apply, expected_rotation=args.expected_rotation)


if __name__ == "__main__":
    main()
