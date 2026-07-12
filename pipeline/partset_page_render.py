"""Render per-partset page images by rotating score cache pages."""

from __future__ import annotations

from typing import Literal

from PIL import Image

from pipeline.page_dimensions import Orientation, get_dimensions
from pipeline.partset_orientation import layout_orientation, normalize_rotation_degrees

PageKind = Literal["lowres", "highres", "thumbs"]


def rotate_page_image(source: Image.Image, rotation_degrees: int) -> Image.Image:
    """Rotate a page image in place — the whole page turns, nothing letterboxed."""
    rotation_degrees = normalize_rotation_degrees(rotation_degrees)
    im = source.convert("L") if source.mode != "L" else source.copy()
    if rotation_degrees:
        im = im.rotate(rotation_degrees, expand=True, fillcolor=255)
    return im


def render_oriented_page(
    source: Image.Image,
    *,
    score_orientation: Orientation,
    rotation_degrees: int,
    kind: PageKind,
) -> Image.Image:
    """Rotate a score page image and resize to the effective layout dimensions."""
    rotation_degrees = normalize_rotation_degrees(rotation_degrees)
    im = source.convert("L") if source.mode != "L" else source.copy()
    if rotation_degrees:
        im = im.rotate(rotation_degrees, expand=True, fillcolor=255)
    layout = layout_orientation(score_orientation, rotation_degrees)
    dims = get_dimensions(layout)
    if kind == "lowres":
        target = dims.lowres_size
    elif kind == "highres":
        target = dims.highres_size
    else:
        target = dims.thumb_size
    return im.resize(target, Image.LANCZOS)
