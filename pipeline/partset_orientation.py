"""Per-partset score page orientation (override + cardinal rotation)."""

from __future__ import annotations

from pipeline.page_dimensions import Orientation

ROTATION_OPTIONS: tuple[int, ...] = (0, 90, 180, 270)


def normalize_rotation_degrees(degrees: int) -> int:
    value = int(degrees) % 360
    if value not in ROTATION_OPTIONS:
        raise ValueError(f"rotation_degrees must be one of {ROTATION_OPTIONS}")
    return value


def layout_orientation(base_orientation: Orientation, rotation_degrees: int) -> Orientation:
    """Portrait/landscape layout after applying cardinal rotation to page images."""
    rotation_degrees = normalize_rotation_degrees(rotation_degrees)
    base: Orientation = "landscape" if base_orientation == "landscape" else "portrait"
    if rotation_degrees % 180 == 90:
        return "landscape" if base == "portrait" else "portrait"
    return base


def effective_partset_orientation(
    *,
    score_orientation: Orientation | str | None,
    orientation_override: Orientation | str | None,
    rotation_degrees: int,
) -> Orientation:
    base: Orientation = "landscape" if score_orientation == "landscape" else "portrait"
    if orientation_override in ("portrait", "landscape"):
        return str(orientation_override)  # type: ignore[return-value]
    if rotation_degrees:
        return layout_orientation(base, rotation_degrees)
    return base


def partset_uses_custom_pages(rotation_degrees: int) -> bool:
    return normalize_rotation_degrees(rotation_degrees) != 0
