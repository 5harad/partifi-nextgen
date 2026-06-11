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
from pipeline.cut_segments import cut_segment_tasks, default_pool_size
from pipeline.cutpaste import (
    apply_combined_parts,
    build_part_segment_map,
    compute_cues,
    page_chunks,
    prct2pixel,
)
from pipeline.paste_segments import create_parts
from local_cache import get_local_cache
from s3_storage import upload_file

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
    return {row.tag: float(row.spacing or 0.1) for row in rows}


def _fetch_part_files(partset_id: str) -> list[dict]:
    rows = fetchall(
        "SELECT tag, file_name, spacing FROM parts WHERE partset_id = :partset_id ORDER BY combined, tag",
        {"partset_id": partset_id},
    )
    return [{"tag": row.tag, "file_name": row.file_name, "spacing": float(row.spacing or 0.1)} for row in rows]


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


def run_gen_parts(partset_id: str) -> None:
    workdir = Path(f"/tmp/partifi/{partset_id}/gen")
    try:
        _run_gen_parts(partset_id, workdir)
    except Exception:
        logger.exception("Part generation failed for partset %s", partset_id)
        mark_partset_error(partset_id)
        raise
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _run_gen_parts(partset_id: str, workdir: Path) -> None:
    partset = fetchone(
        "SELECT score_id, title, composer FROM partsets WHERE id = :id",
        {"id": partset_id},
    )
    if not partset or not partset.score_id:
        logger.error("Invalid partset %s", partset_id)
        return

    score_id = partset.score_id
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
        execute(
            "UPDATE partsets SET parts_ready = 1, mod_ts = NOW() WHERE id = :id",
            {"id": partset_id},
        )
        return

    execute(
        "UPDATE partsets SET status = 'cut', cut_start = NOW(), cut_progress = 0, "
        "paste_start = NULL, paste_complete = NULL, paste_progress = 0 WHERE id = :id",
        {"id": partset_id},
    )

    pages_needed = sorted({row["page"] for row in segment_rows})
    cache = get_local_cache()
    for page in pages_needed:
        local_page = pages_dir / f"page-{page}.png"
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

    segment_heights = [prct2pixel(h) for h in heights_pct]
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
        chunks = page_chunks(seg_list, segment_heights, spacing_px, breakpoints)

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
        for pagesize, prefix in (("letter", ""), ("a4", "a4_")):
            outfile = outdir / f"{partset_id}_{prefix}{part_row['file_name']}"
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
                }
            )

    num_paste = len(paste_jobs) or 1
    paste_inc = 100.0 / num_paste
    create_parts(
        paste_jobs,
        pool_size=_pool_size(len(paste_jobs)),
        on_part_done=lambda: _update_paste_progress(partset_id, paste_inc),
    )

    for path in outdir.glob("*.pdf"):
        key = f"parts/{partset_id}/{path.name}"
        cache.store_part_file(partset_id, path)
        upload_file(path, key, "application/pdf")

    execute(
        "UPDATE partsets SET paste_complete = NOW(), parts_ready = 1, mod_ts = NOW() WHERE id = :id",
        {"id": partset_id},
    )

    logger.info("Part generation complete for %s", partset_id)
