"""Reorient a partset's page images without changing score-level orientation."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from PIL import Image

from find_segments import analyze_score
from import_lock import release_import_lock
from jobs.errors import mark_partset_error
from local_cache import ensure_lowres_files, get_local_cache
from pipeline.partset_orientation import (
    layout_orientation,
    normalize_rotation_degrees,
    orientation_override_for_rotation,
    partset_uses_custom_pages,
)
from pipeline.partset_page_render import render_oriented_page
from score_cache import fetch_score_orientation
from split_two_up import split_two_up_pdf

import db_conn

logger = logging.getLogger("partifi.reorient_partset")


def _reset_partset_for_reorient(partset_id: str) -> None:
    db_conn.execute(
        "DELETE FROM segments WHERE partset_id = :partset_id",
        {"partset_id": partset_id},
    )
    db_conn.execute(
        "DELETE FROM pages WHERE partset_id = :partset_id",
        {"partset_id": partset_id},
    )
    db_conn.execute(
        "DELETE FROM parts WHERE partset_id = :partset_id",
        {"partset_id": partset_id},
    )
    db_conn.execute(
        "UPDATE partsets SET "
        "status = 'convert', convert_start = NOW(), convert_complete = NULL, convert_progress = 0, "
        "analysis_start = NULL, analysis_complete = NULL, analysis_progress = 0, "
        "cut_start = NULL, cut_complete = NULL, cut_progress = 0, "
        "paste_start = NULL, paste_complete = NULL, paste_progress = 0, "
        "parts_ready = 0, error = NULL, error_message = NULL, error_ts = NULL "
        "WHERE id = :id",
        {"id": partset_id},
    )


def _fetch_num_pages(score_id: str) -> int:
    row = db_conn.fetchone(
        "SELECT num_pages FROM scores WHERE id = :id",
        {"id": score_id},
    )
    if not row or not row.num_pages:
        raise RuntimeError(f"Score {score_id} has no pages")
    return int(row.num_pages)


def _ensure_score_highres_pages(score_id: str, *, job_id: str | None = None) -> None:
    cache = get_local_cache()
    if cache.score_has_kind(score_id, "highres"):
        return
    from score_page_cache import build_score_page_cache

    build_score_page_cache(score_id, job_id=job_id)


def _render_partset_pages(
    *,
    score_id: str,
    score_orientation: str,
    rotation_degrees: int,
    pages_dir: Path,
    num_pages: int,
    partset_id: str | None = None,
    job_id: str | None = None,
) -> list[str]:
    _ensure_score_highres_pages(score_id, job_id=job_id)
    cache = get_local_cache()
    lowres_files: list[str] = []
    for page in range(1, num_pages + 1):
        source = Image.open(cache.ensure_score_page(score_id, "highres", page))
        for kind in ("highres", "lowres", "thumbs"):
            out_dir = pages_dir / kind
            out_dir.mkdir(parents=True, exist_ok=True)
            rendered = render_oriented_page(
                source,
                score_orientation=score_orientation,  # type: ignore[arg-type]
                rotation_degrees=rotation_degrees,
                kind=kind,
            )
            out_path = out_dir / f"page-{page}.png"
            rendered.save(out_path)
            if kind == "lowres":
                lowres_files.append(str(out_path))
        if partset_id is not None:
            db_conn.execute(
                "UPDATE partsets SET convert_progress = :progress WHERE id = :id",
                {"progress": 100.0 * page / num_pages, "id": partset_id},
            )
    return sorted(lowres_files)


def _render_split_two_up_pages(
    *,
    score_id: str,
    rotation_degrees: int,
    pages_dir: Path,
    partset_id: str | None = None,
) -> list[str]:
    """Split a viewer-oriented score PDF, then use the normal raster pipeline."""
    from pdf2png import par_pdf2png

    cache = get_local_cache()
    derived_pdf = pages_dir.parent / "split-two-up.pdf"
    split_two_up_pdf(
        cache.ensure_score_pdf(score_id),
        derived_pdf,
        rotation_degrees=rotation_degrees,
    )
    par_pdf2png(
        str(derived_pdf),
        str(pages_dir),
        partset_id,
        orientation="portrait",
    )
    return [str(path) for path in sorted((pages_dir / "lowres").glob("*.png"))]


def rebuild_partset_page_cache(
    partset_id: str,
    score_id: str,
    rotation_degrees: int,
    *,
    split_two_up: bool = False,
    workdir: Path,
    job_id: str | None = None,
) -> None:
    """Render rotated score pages into the partset page cache."""
    rotation_degrees = normalize_rotation_degrees(rotation_degrees)
    if not (split_two_up or partset_uses_custom_pages(rotation_degrees)):
        return
    pages_dir = workdir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    if split_two_up:
        _render_split_two_up_pages(
            score_id=score_id,
            rotation_degrees=rotation_degrees,
            pages_dir=pages_dir,
        )
    else:
        _render_partset_pages(
            score_id=score_id,
            score_orientation=fetch_score_orientation(score_id),
            rotation_degrees=rotation_degrees,
            pages_dir=pages_dir,
            num_pages=_fetch_num_pages(score_id),
            job_id=job_id,
        )
    get_local_cache().copy_partset_pages_tree(partset_id, pages_dir)


def run_reorient_partset(
    partset_id: str,
    score_id: str,
    rotation_degrees: int,
    *,
    split_two_up: bool = False,
    job_id: str | None = None,
) -> None:
    rotation_degrees = normalize_rotation_degrees(rotation_degrees)
    gs_orientation = fetch_score_orientation(score_id)
    effective = "portrait" if split_two_up else layout_orientation(gs_orientation, rotation_degrees)

    suffix = job_id or "unknown"
    workdir = Path(f"/tmp/partifi/{partset_id}/reorient-{suffix}")
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    cache = get_local_cache()
    try:
        _reset_partset_for_reorient(partset_id)
        cache.invalidate_preview(partset_id)
        cache.invalidate_parts(partset_id)
        cache.invalidate_partset_pages(partset_id)

        pages_dir = workdir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Reorienting partset %s (gs_orientation=%s rotation=%s effective=%s)",
            partset_id,
            gs_orientation,
            rotation_degrees,
            effective,
        )

        if split_two_up:
            lowres_files = _render_split_two_up_pages(
                score_id=score_id,
                rotation_degrees=rotation_degrees,
                pages_dir=pages_dir,
                partset_id=partset_id,
            )
            cache.copy_partset_pages_tree(partset_id, pages_dir)
        elif partset_uses_custom_pages(rotation_degrees):
            lowres_files = _render_partset_pages(
                score_id=score_id,
                score_orientation=gs_orientation,
                rotation_degrees=rotation_degrees,
                pages_dir=pages_dir,
                num_pages=_fetch_num_pages(score_id),
                partset_id=partset_id,
                job_id=job_id,
            )
            cache.copy_partset_pages_tree(partset_id, pages_dir)
        else:
            lowres_files = [str(p) for p in ensure_lowres_files(score_id)]
            db_conn.execute(
                "UPDATE partsets SET convert_progress = 100 WHERE id = :id",
                {"id": partset_id},
            )

        db_conn.execute(
            "UPDATE partsets SET orientation_override = :orientation, rotation_degrees = :rotation, "
            "split_two_up = :split_two_up "
            "WHERE id = :id",
            {
                "orientation": "portrait"
                if split_two_up
                else orientation_override_for_rotation(gs_orientation, rotation_degrees),
                "rotation": rotation_degrees,
                "split_two_up": split_two_up,
                "id": partset_id,
            },
        )

        db_conn.execute(
            "UPDATE partsets SET convert_complete = NOW(), convert_progress = 100 WHERE id = :id",
            {"id": partset_id},
        )

        analyze_score(partset_id, lowres_files)

        db_conn.execute(
            "UPDATE partsets SET last_access = NOW() WHERE id = :id",
            {"id": partset_id},
        )
        logger.info("Reorient complete for partset %s", partset_id)
    except Exception as exc:
        logger.exception("Reorient failed for partset %s", partset_id)
        mark_partset_error(partset_id, message=str(exc), job_id=job_id)
        raise
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        release_import_lock(partset_id)
