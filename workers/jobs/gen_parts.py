"""Generate part PDFs: highres cut + paste."""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent
for root in (APP_ROOT, REPO_ROOT):
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

from db_conn import execute, fetchall, fetchone
from config import get_settings
from jobs.errors import mark_partset_error
from pipeline.cut_segments import cut_segment_tasks, read_segment_png_heights, default_pool_size
from pipeline.page_dimensions import Orientation
from pipeline.part_filenames import resolve_part_filename
from pipeline.cutpaste import (
    apply_combined_parts,
    build_part_segment_map,
    compute_cues,
    page_chunks,
)
from pipeline.paste_segments import create_parts
from gen_parts_lock import release_gen_parts_lock
from score_page_cache import build_score_page_cache
from local_cache import get_local_cache
from pipeline.partset_orientation import partset_uses_custom_pages
from score_cache import fetch_partset_effective_orientation, fetch_score_orientation

logger = logging.getLogger("partifi.gen_parts")


def _pool_size(num_tasks: int) -> int:
    settings = get_settings()
    if settings.partgen_pool_size > 0:
        return max(1, min(settings.partgen_pool_size, num_tasks))
    return default_pool_size(num_tasks)


def _fetch_segment_rows(partset_id: str) -> list[dict]:
    rows = fetchall(
        """
        SELECT pages.page AS page, rotation, left_margin, right_margin, top, bottom, tags, label
        FROM pages
        JOIN segments ON pages.partset_id = segments.partset_id AND pages.page = segments.page
        WHERE pages.partset_id = :partset_id
          AND tags IS NOT NULL AND tags != ''
        ORDER BY page, top
        """,
        {"partset_id": partset_id},
    )
    return [
        {
            "page": row.page,
            "rotation": float(row.rotation or 0),
            "left_margin": float(row.left_margin or 0),
            "right_margin": float(row.right_margin or 100),
            "top": float(row.top or 0),
            "bottom": float(row.bottom or 0),
            "tags": row.tags,
            "label": row.label,
        }
        for row in rows
    ]


def _fetch_combined_tags(partset_id: str) -> list[str]:
    rows = fetchall(
        "SELECT tag FROM parts WHERE combined = 1 AND partset_id = :partset_id",
        {"partset_id": partset_id},
    )
    return [row.tag for row in rows]


def _fetch_breaks(partset_id: str) -> dict[str, list[int]]:
    rows = fetchall(
        "SELECT tag, `break` FROM breaks WHERE partset_id = :partset_id",
        {"partset_id": partset_id},
    )
    breaks: dict[str, list[int]] = {}
    for row in rows:
        brk_val = row._mapping["break"]
        breaks.setdefault(row.tag, []).append(int(brk_val))
    return breaks


def _fetch_spacings(partset_id: str) -> dict[str, float]:
    rows = fetchall(
        "SELECT tag, spacing FROM parts WHERE partset_id = :partset_id",
        {"partset_id": partset_id},
    )
    return {
        row.tag: float(row.spacing if row.spacing is not None else 0.1)
        for row in rows
    }


def _fetch_part_files(partset_id: str) -> list[dict]:
    rows = fetchall(
        "SELECT tag, file_name, spacing, combined FROM parts "
        "WHERE partset_id = :partset_id ORDER BY combined, tag",
        {"partset_id": partset_id},
    )
    return [
        {
            "tag": row.tag,
            "file_name": row.file_name,
            "spacing": float(row.spacing if row.spacing is not None else 0.1),
            "combined": bool(row.combined),
        }
        for row in rows
    ]


def _update_cut_progress(partset_id: str, increment: float) -> None:
    execute(
        "UPDATE partsets SET cut_progress = cut_progress + :inc WHERE id = :id",
        {"inc": increment, "id": partset_id},
    )


def _update_paste_progress(partset_id: str, increment: float) -> None:
    execute(
        "UPDATE partsets SET paste_progress = paste_progress + :inc WHERE id = :id",
        {"inc": increment, "id": partset_id},
    )


def run_gen_parts(partset_id: str, *, job_id: str | None = None) -> None:
    suffix = job_id or "unknown"
    workdir = Path(f"/tmp/partifi/{partset_id}/gen-{suffix}")
    try:
        _run_gen_parts(partset_id, workdir, job_id=job_id)
    except Exception as exc:
        logger.exception("Part generation failed for partset %s", partset_id)
        mark_partset_error(partset_id, message=str(exc), job_id=job_id)
        raise
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        release_gen_parts_lock(partset_id)


def _run_gen_parts(partset_id: str, workdir: Path, *, job_id: str | None = None) -> None:
    partset = fetchone(
        "SELECT score_id, title, composer FROM partsets WHERE id = :id",
        {"id": partset_id},
    )
    if not partset or not partset.score_id:
        msg = f"Invalid partset {partset_id}"
        logger.error(msg)
        raise ValueError(msg)

    score_id = partset.score_id
    orientation = fetch_partset_effective_orientation(partset_id, score_id)
    orient: Orientation = "landscape" if orientation == "landscape" else "portrait"
    if workdir.exists():
        shutil.rmtree(workdir)
    pages_dir = workdir / "pages"
    segments_dir = workdir / "segments"
    outdir = workdir / "parts"
    pages_dir.mkdir(parents=True)
    segments_dir.mkdir(parents=True)
    outdir.mkdir(parents=True)

    segment_rows = _fetch_segment_rows(partset_id)
    if not segment_rows:
        part_count = fetchone(
            "SELECT COUNT(*) AS n FROM parts WHERE partset_id = :id",
            {"id": partset_id},
        )
        if part_count and part_count.n == 0:
            execute(
                "UPDATE partsets SET parts_ready = 1, mod_ts = NOW() WHERE id = :id",
                {"id": partset_id},
            )
        return

    pages_needed = sorted({row["page"] for row in segment_rows})
    cache = get_local_cache()
    rotation_row = fetchone(
        "SELECT rotation_degrees FROM partsets WHERE id = :id",
        {"id": partset_id},
    )
    rotation_degrees = int(rotation_row.rotation_degrees or 0) if rotation_row else 0
    uses_partset_pages = partset_uses_custom_pages(rotation_degrees)
    if uses_partset_pages and not cache.partset_has_kind(partset_id, "highres"):
        raise RuntimeError(
            f"Rotated page images missing from cache for partset {partset_id}; reorient the score"
        )
    if not uses_partset_pages and not cache.score_has_kind(score_id, "highres"):
        logger.info("Score %s highres pages missing from cache; warming from PDF", score_id)
        execute(
            "UPDATE partsets SET status = 'convert', convert_progress = 0, "
            "cut_start = NULL, cut_complete = NULL, cut_progress = 0, "
            "paste_start = NULL, paste_complete = NULL, paste_progress = 0 WHERE id = :id",
            {"id": partset_id},
        )
        build_score_page_cache(score_id, job_id=job_id)

    execute(
        "UPDATE partsets SET status = 'cut', cut_start = NOW(), cut_progress = 0, "
        "paste_start = NULL, paste_complete = NULL, paste_progress = 0 WHERE id = :id",
        {"id": partset_id},
    )

    for page in pages_needed:
        local_page = pages_dir / f"page-{page}.png"
        if uses_partset_pages:
            cached = cache.ensure_partset_page(partset_id, "highres", page)
        else:
            cached = cache.ensure_score_page(score_id, "highres", page)
        local_page.write_bytes(cached.read_bytes())

    cut_tasks: list[tuple[Path, float, float, float, float, float, Path]] = []
    for ndx, row in enumerate(segment_rows):
        page_path = pages_dir / f"page-{row['page']}.png"
        out_path = segments_dir / f"s{ndx}.png"
        cut_tasks.append(
            (
                page_path,
                row["rotation"],
                row["left_margin"],
                row["top"],
                row["right_margin"],
                row["bottom"],
                out_path,
            )
        )

    num_cut_pages = len({task[0] for task in cut_tasks})
    cut_inc = 100.0 / max(num_cut_pages, 1)
    cut_segment_tasks(
        cut_tasks,
        pool_size=_pool_size(num_cut_pages),
        on_page_done=lambda: _update_cut_progress(partset_id, cut_inc),
    )

    execute(
        "UPDATE partsets SET cut_complete = NOW() WHERE id = :id",
        {"id": partset_id},
    )

    segments_map, heights_pct, _widths_pct, labels = build_part_segment_map(segment_rows)
    combined_tags = _fetch_combined_tags(partset_id)
    apply_combined_parts(segments_map, combined_tags)

    segment_heights = read_segment_png_heights(segments_dir, len(segment_rows))
    breaks = _fetch_breaks(partset_id)
    spacings = _fetch_spacings(partset_id)
    part_rows = _fetch_part_files(partset_id)

    execute(
        "UPDATE partsets SET status = 'paste', paste_start = NOW(), paste_progress = 0 WHERE id = :id",
        {"id": partset_id},
    )

    paste_jobs = []
    for part_row in part_rows:
        tag = part_row["tag"]
        if tag not in segments_map:
            continue
        seg_list = segments_map[tag]
        breakpoints = breaks.get(tag, [])
        spacing_px = round(spacings.get(tag, 0.1) * 300)
        cues = compute_cues(tag, segments_map)
        chunks = page_chunks(seg_list, segment_heights, spacing_px, breakpoints, orientation=orientation)

        pages: list[list[dict]] = []
        for chunk in chunks:
            page_segs = []
            for seg_id in chunk:
                page_segs.append(
                    {
                        "file": segments_dir / f"s{seg_id}.png",
                        "label": labels[seg_id],
                        "cue": seg_id in cues,
                    }
                )
            pages.append(page_segs)

        part_name = tag
        file_name = resolve_part_filename(
            part_row["file_name"] or "",
            tag,
            combined=part_row["combined"],
        )
        if file_name != (part_row["file_name"] or ""):
            execute(
                "UPDATE parts SET file_name = :file_name "
                "WHERE partset_id = :partset_id AND tag = :tag",
                {"file_name": file_name, "partset_id": partset_id, "tag": tag},
            )
        for pagesize, prefix in (("letter", ""), ("a4", "a4_")):
            outfile = outdir / f"{partset_id}_{prefix}{file_name}"
            paste_jobs.append(
                {
                    "title": partset.title or "",
                    "composer": partset.composer or "",
                    "part_name": part_name,
                    "partset_id": partset_id,
                    "sep": spacings.get(tag, 0.1),
                    "pages": pages,
                    "outfile": outfile,
                    "pagesize": pagesize,
                    "orientation": orient,
                }
            )

    num_paste = len(paste_jobs) or 1
    paste_inc = 100.0 / num_paste
    if part_rows and not paste_jobs:
        raise RuntimeError(f"No part PDFs to generate for {partset_id}")

    expected_names = [job["outfile"].name for job in paste_jobs]
    create_parts(
        paste_jobs,
        pool_size=_pool_size(len(paste_jobs)),
        on_part_done=lambda: _update_paste_progress(partset_id, paste_inc),
    )

    for path in outdir.glob("*.pdf"):
        cache.store_part_file(partset_id, path)

    missing = [
        name for name in expected_names if not cache.part_is_cached(partset_id, name)
    ]
    if missing:
        msg = f"Part cache incomplete for {partset_id}: {missing}"
        logger.error(msg)
        raise RuntimeError(msg)

    execute(
        "UPDATE partsets SET paste_complete = NOW(), parts_ready = 1, mod_ts = NOW(), "
        "error = NULL, error_message = NULL, error_ts = NULL, last_job_id = NULL "
        "WHERE id = :id",
        {"id": partset_id},
    )

    logger.info("Part generation complete for %s", partset_id)
