"""Re-orient a partset's page images without changing score-level orientation."""

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
    partset_uses_custom_pages,
)
from pipeline.partset_page_render import render_oriented_page
from score_cache import fetch_score_orientation

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


def _render_partset_pages(
    *,
    score_id: str,
    score_orientation: str,
    rotation_degrees: int,
    pages_dir: Path,
    num_pages: int,
    partset_id: str | None = None,
) -> list[str]:
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


def rebuild_partset_page_cache(
    partset_id: str,
    score_id: str,
    rotation_degrees: int,
    *,
    workdir: Path,
) -> None:
    """Render rotated score pages into the partset page cache."""
    rotation_degrees = normalize_rotation_degrees(rotation_degrees)
    if not partset_uses_custom_pages(rotation_degrees):
        return
    gs_orientation = fetch_score_orientation(score_id)
    num_pages = _fetch_num_pages(score_id)
    pages_dir = workdir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    _render_partset_pages(
        score_id=score_id,
        score_orientation=gs_orientation,
        rotation_degrees=rotation_degrees,
        pages_dir=pages_dir,
        num_pages=num_pages,
    )
    get_local_cache().copy_partset_pages_tree(partset_id, pages_dir)


def run_reorient_partset(
    partset_id: str,
    score_id: str,
    rotation_degrees: int,
    *,
    job_id: str | None = None,
) -> None:
    rotation_degrees = normalize_rotation_degrees(rotation_degrees)
    gs_orientation = fetch_score_orientation(score_id)
    effective = layout_orientation(gs_orientation, rotation_degrees)

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

        num_pages = _fetch_num_pages(score_id)
        pages_dir = workdir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Re-orienting partset %s (gs_orientation=%s rotation=%s effective=%s)",
            partset_id,
            gs_orientation,
            rotation_degrees,
            effective,
        )

        if partset_uses_custom_pages(rotation_degrees):
            lowres_files = _render_partset_pages(
                score_id=score_id,
                score_orientation=gs_orientation,
                rotation_degrees=rotation_degrees,
                pages_dir=pages_dir,
                num_pages=num_pages,
                partset_id=partset_id,
            )
            cache.copy_partset_pages_tree(partset_id, pages_dir)
        else:
            lowres_files = [str(p) for p in ensure_lowres_files(score_id)]
            db_conn.execute(
                "UPDATE partsets SET convert_progress = 100 WHERE id = :id",
                {"id": partset_id},
            )

        db_conn.execute(
            "UPDATE partsets SET orientation_override = :orientation, rotation_degrees = :rotation "
            "WHERE id = :id",
            {"orientation": effective, "rotation": rotation_degrees, "id": partset_id},
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
        logger.info("Re-orient complete for partset %s", partset_id)
    except Exception as exc:
        logger.exception("Re-orient failed for partset %s", partset_id)
        mark_partset_error(partset_id, message=str(exc), job_id=job_id)
        raise
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        release_import_lock(partset_id)
