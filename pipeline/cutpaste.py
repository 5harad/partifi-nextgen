"""Layout helpers ported from legacy cutpaste.php."""

from __future__ import annotations

from pipeline.page_dimensions import Orientation, get_dimensions, prct2pixel as _prct2pixel
from pipeline.paste_layout import paste_page_chunk_max_px

ALL_TAG_KEYS = ("all", "All", "ALL")


def prct2pixel(
    p: float,
    dim: str = "height",
    orientation: Orientation = "portrait",
) -> float:
    return _prct2pixel(p, dim, orientation)


def chunk_stack_height_px(
    segment_indices: list[int],
    heights: list[float],
    spacing_px: float,
) -> float:
    """Pixel height of stacked segments plus inter-segment spacing (300 dpi)."""
    if not segment_indices:
        return 0.0
    total = sum(heights[i] for i in segment_indices)
    if len(segment_indices) > 1:
        total += spacing_px * (len(segment_indices) - 1)
    return total


def page_chunks(
    segments: list[int],
    heights: list[float],
    spacing: float,
    breaks: list[int] | None = None,
    *,
    orientation: Orientation = "portrait",
) -> list[list[int]]:
    breaks_set = set(breaks or [])
    max_h = paste_page_chunk_max_px(orientation)
    chunks: list[list[int]] = []
    current: list[int] = []

    for i, seg_id in enumerate(segments):
        if i - 1 in breaks_set and current:
            chunks.append(current)
            current = []

        candidate = current + [seg_id]
        if current and chunk_stack_height_px(candidate, heights, spacing) > max_h:
            chunks.append(current)
            current = [seg_id]
        else:
            current = candidate

    if current:
        chunks.append(current)
    return chunks


def parse_tag_list(tags: str | None) -> list[str]:
    if not tags:
        return []
    return [t.strip() for t in tags.split(",") if t.strip() and t.strip() != "(none)"]


def build_part_segment_map(
    segment_rows: list[dict],
) -> tuple[dict[str, list[int]], list[float], list[float], list[str]]:
    """Build part -> segment indices map and per-segment metadata."""
    segments: dict[str, list[int]] = {}
    heights: list[float] = []
    widths: list[float] = []
    labels: list[str] = []

    all_indices: list[int] = []

    for ndx, row in enumerate(segment_rows):
        tags = parse_tag_list(row.get("tags"))
        for tag in tags:
            if tag in ALL_TAG_KEYS:
                all_indices.append(ndx)
            else:
                segments.setdefault(tag, []).append(ndx)

        label = row.get("label") or ""
        if label == "(none)":
            label = ""
        heights.append(float(row["bottom"]) - float(row["top"]))
        widths.append(float(row["right_margin"]) - float(row["left_margin"]))
        labels.append(label)

    all_indices = sorted(set(all_indices))

    if all_indices:
        for part in list(segments.keys()):
            merged = sorted(set(segments[part] + all_indices))
            segments[part] = merged

    return segments, heights, widths, labels


def apply_combined_parts(
    segments: dict[str, list[int]],
    combined_tags: list[str],
) -> None:
    for tag in combined_tags:
        merged: list[int] = []
        for part in tag.split(" + "):
            merged.extend(segments.get(part, []))
        segments[tag] = sorted(set(merged))


def compute_cues(part_name: str, part_segments: dict[str, list[int]]) -> set[int]:
    cue_segs: list[int] = []
    non_cue_segs: list[int] = []
    for piece in part_name.split(" + "):
        if piece.endswith(" cue"):
            cue_segs.extend(part_segments.get(piece, []))
        else:
            non_cue_segs.extend(part_segments.get(piece, []))
    return set(cue_segs) - set(non_cue_segs)


def preview_left_margin_px(
    max_width_px: float,
    orientation: Orientation = "portrait",
    pagesize: str = "letter",
) -> int:
    """Preview-pane pixels for paste left_margin — mirrors paste_segments.create_part."""
    from pipeline.paste_layout import RESOLUTION, page_dims_inches

    page_w, _ = page_dims_inches(pagesize, orientation)
    dims = get_dimensions(orientation)
    left_in = max(0, (page_w - max_width_px / RESOLUTION) / 2)
    return round(left_in / page_w * dims.preview_pane_width)


def preview_left_margin(
    widths_pct: list[float],
    orientation: Orientation = "portrait",
) -> int:
    if not widths_pct:
        return 0
    max_width_px = max(prct2pixel(w, "width", orientation=orientation) for w in widths_pct)
    return preview_left_margin_px(max_width_px, orientation)
