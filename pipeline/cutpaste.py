"""Layout helpers ported from legacy cutpaste.php."""

from __future__ import annotations

HIGHRES_HEIGHT = 3300
HIGHRES_WIDTH = 2550
PAGE_CHUNK_MAX = 2900
ALL_TAG_KEYS = ("all", "All", "ALL")


def prct2pixel(p: float, dim: str = "height") -> float:
    scale = HIGHRES_HEIGHT if dim == "height" else HIGHRES_WIDTH
    return p / 100.0 * scale


def page_chunks(
    segments: list[int],
    heights: list[float],
    spacing: float,
    breaks: list[int] | None = None,
) -> list[list[int]]:
    breaks = breaks or []
    chunks: list[list[int]] = []
    start = 0
    h = 0.0
    for i, seg_id in enumerate(segments):
        seg_h = heights[seg_id]
        if h + seg_h >= PAGE_CHUNK_MAX or (i - 1) in breaks:
            chunks.append(segments[start:i])
            start = i
            h = 0.0
        h += seg_h + spacing
    chunks.append(segments[start:])
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

    for ndx, row in enumerate(segment_rows):
        tags = parse_tag_list(row.get("tags"))
        tags = [t for t in tags if t not in ALL_TAG_KEYS]
        for tag in tags:
            segments.setdefault(tag, []).append(ndx)

        label = row.get("label") or ""
        if label == "(none)":
            label = ""
        heights.append(float(row["bottom"]) - float(row["top"]))
        widths.append(float(row["right_margin"]) - float(row["left_margin"]))
        labels.append(label)

    all_indices: list[int] = []
    for key in ALL_TAG_KEYS:
        if key in segments:
            all_indices.extend(segments.pop(key))
    all_indices = sorted(set(all_indices))

    for part in list(segments.keys()):
        merged = sorted(set(segments[part] + all_indices))
        segments[part] = merged

    part_names = sorted(segments.keys())
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


def preview_left_margin(widths_pct: list[float]) -> int:
    if not widths_pct:
        return 0
    return round((1 - max(widths_pct) / 100.0) / 2 * 367)
