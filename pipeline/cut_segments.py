"""Cut score page images into segment PNGs (Python 3 port of legacy cut_segments.py)."""

from __future__ import annotations

import os
from collections import defaultdict
from collections.abc import Callable
from multiprocessing import Pool
from pathlib import Path

from PIL import Image


def _percent2abs(percent: float, scale: int) -> int:
    return int(percent / 100.0 * scale)


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
    if workers <= 1:
        for job in jobs:
            _cut_image_job(job)
            if on_page_done:
                on_page_done()
        return

    with Pool(processes=workers) as pool:
        for _ in pool.imap_unordered(_cut_image_job, jobs, chunksize=1):
            if on_page_done:
                on_page_done()
