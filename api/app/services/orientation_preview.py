"""Serve rotated orientation preview thumbnails."""

from __future__ import annotations

import io

from PIL import Image

from app.models import Partset, Score
from app.services.local_cache import get_local_cache
from pipeline.partset_orientation import normalize_rotation_degrees
from pipeline.partset_page_render import rotate_page_image


def render_orientation_preview_png(
    partset: Partset,
    score: Score,
    rotation_degrees: int,
) -> bytes:
    rotation_degrees = normalize_rotation_degrees(rotation_degrees)
    cache = get_local_cache()
    page_path = cache.ensure_score_page(score.id, "lowres", 1)
    im = rotate_page_image(Image.open(page_path), rotation_degrees)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()
