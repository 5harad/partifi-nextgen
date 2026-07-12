"""Cut score page images into segment PNGs (Python 3 port of legacy cut_segments.py)."""

from __future__ import annotations

import os
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

from PIL import Image

from pipeline.page_dimensions import Orientation, get_dimensions
from pipeline.parallel import run_in_parallel


def _percent2abs(percent: float, scale: int) -> int:
    return int(percent / 100.0 * scale)


def segment_cut_height_px(
    top_pct: float,
    bottom_pct: float,
    orientation: Orientation = "portrait",
    *,
    page_height_px: int | None = None,
) -> int:
    """Pixel height of a cut segment — matches cut_segments_on_image crop math."""
    page_h = (
        page_height_px
        if page_height_px is not None
        else get_dimensions(orientation).highres_height
    )
    top_px = _percent2abs(top_pct, page_h)
    bottom_px = max(_percent2abs(bottom_pct, page_h), top_px + 1)
    return bottom_px - top_px


def read_segment_png_heights(segments_dir: Path, count: int) -> list[float]:
    heights: list[float] = []
    for ndx in range(count):
        with Image.open(segments_dir / f"s{ndx}.png") as im:
            heights.append(float(im.size[1]))
    return heights


def segment_heights_for_rows(
    segment_rows: list[dict],
    orientation: Orientation,
    page_heights_px: dict[int, int],
) -> list[float]:
    """Highres segment heights using each source page's actual pixel height."""
    return [
        float(
            segment_cut_height_px(
                float(row["top"]),
                float(row["bottom"]),
                orientation,
                page_height_px=page_heights_px[int(row["page"])],
            )
        )
        for row in segment_rows
    ]


def scaled_preview_segment_heights(
    preview_dir: Path,
    segment_rows: list[dict],
    *,
    highres_page_heights: dict[int, int],
    lowres_page_heights: dict[int, int],
) -> list[float]:
    """Measure preview segment PNGs (lowres cuts) scaled to highres for gen_parts parity."""
    heights = read_segment_png_heights(preview_dir, len(segment_rows))
    scaled: list[float] = []
    for i, row in enumerate(segment_rows):
        page = int(row["page"])
        lowres_h = lowres_page_heights.get(page)
        highres_h = highres_page_heights.get(page)
        if not lowres_h or not highres_h:
            raise ValueError(f"Missing page heights for page {page}")
        scaled.append(heights[i] * (highres_h / lowres_h))
    return scaled


def cut_segments_on_image(
    imfile: Path,
    rotation: float,
    segments: list[tuple[float, float, float, float, Path]],
) -> None:
    im = Image.open(imfile).convert("L")
    width, height = im.size

    if rotation:
        mask = Image.new("L", im.size, 255)
        rotated = Image.new("L", im.size, 255)
        rotated.paste(im.rotate(rotation, Image.Resampling.BILINEAR), mask.rotate(rotation))
        im = rotated

    for left, top, right, bottom, outfile in segments:
        top_px = _percent2abs(top, height)
        left_px = _percent2abs(left, width)
        bottom_px = max(_percent2abs(bottom, height), top_px + 1)
        right_px = max(_percent2abs(right, width), left_px + 1)
        segment = im.crop((left_px, top_px, right_px, bottom_px))
        outfile.parent.mkdir(parents=True, exist_ok=True)
        segment.save(outfile)


def _group_cut_tasks(
    tasks: list[tuple[Path, float, float, float, float, float, Path]],
) -> list[tuple[str, float, list[tuple[float, float, float, float, str]]]]:
    by_image: dict[Path, list[tuple[float, float, float, float, str]]] = defaultdict(list)
    rotation_by_image: dict[Path, float] = {}
    for imfile, rotation, left, top, right, bottom, outfile in tasks:
        rotation_by_image[imfile] = rotation
        by_image[imfile].append((left, top, right, bottom, str(outfile)))

    return [
        (str(imfile), rotation_by_image[imfile], segments)
        for imfile, segments in by_image.items()
    ]


def _cut_image_job(args: tuple[str, float, list[tuple[float, float, float, float, str]]]) -> None:
    imfile, rotation, segments = args
    cut_segments_on_image(
        Path(imfile),
        rotation,
        [(left, top, right, bottom, Path(outfile)) for left, top, right, bottom, outfile in segments],
    )


def default_pool_size(num_tasks: int) -> int:
    if num_tasks <= 1:
        return 1
    return max(1, min(num_tasks, (os.cpu_count() or 2) // 2))


def cut_segment_tasks(
    tasks: list[tuple[Path, float, float, float, float, float, Path]],
    *,
    pool_size: int | None = None,
    on_page_done: Callable[[], None] | None = None,
) -> None:
    jobs = _group_cut_tasks(tasks)
    if not jobs:
        return

    workers = pool_size if pool_size is not None else default_pool_size(len(jobs))
    run_in_parallel(_cut_image_job, jobs, workers=workers, on_done=on_page_done)
