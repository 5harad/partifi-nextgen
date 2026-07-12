from pipeline.cutpaste import build_part_segment_map, chunk_stack_height_px, page_chunks
from pipeline.paste_layout import paste_page_chunk_max_px


def _row(tags: str, ndx: int) -> dict:
    return {
        "tags": tags,
        "top": float(ndx * 10),
        "bottom": float(ndx * 10 + 10),
        "left_margin": 0.0,
        "right_margin": 100.0,
        "label": "",
    }


def test_all_tag_merged_into_every_part() -> None:
    rows = [_row("violin", 0), _row("all", 1), _row("cello", 2)]
    segments, *_ = build_part_segment_map(rows)

    assert segments["violin"] == [0, 1]
    assert segments["cello"] == [1, 2]
    assert "all" not in segments


def test_all_tag_case_insensitive() -> None:
    rows = [_row("violin", 0), _row("All", 1)]
    segments, *_ = build_part_segment_map(rows)

    assert segments["violin"] == [0, 1]


def test_all_combined_with_part_tag_on_same_segment() -> None:
    rows = [_row("violin, all", 0), _row("cello", 1)]
    segments, *_ = build_part_segment_map(rows)

    assert segments["violin"] == [0]
    assert segments["cello"] == [0, 1]


def test_only_all_tags_yields_no_parts() -> None:
    rows = [_row("all", 0), _row("ALL", 1)]
    segments, *_ = build_part_segment_map(rows)

    assert segments == {}


def test_page_chunks_oversized_first_segment_no_leading_blank() -> None:
    """First segment taller than the content band must not create an empty first page."""
    max_px = paste_page_chunk_max_px("portrait")
    heights = [float(max_px + 100), 500.0, 500.0]
    chunks = page_chunks([0, 1, 2], heights, spacing=30)
    assert chunks[0] == [0]
    assert all(len(c) > 0 for c in chunks)


def test_page_chunks_break_at_minus_one_no_leading_blank() -> None:
    chunks = page_chunks([0, 1, 2], [400.0, 400.0, 400.0], spacing=30, breaks=[-1])
    assert chunks == [[0, 1, 2]]


def test_page_chunks_respects_break_after_first_segment() -> None:
    chunks = page_chunks([0, 1, 2], [400.0, 400.0, 400.0], spacing=30, breaks=[0])
    assert chunks == [[0], [1, 2]]


def test_page_chunks_normal_fit_on_one_page() -> None:
    chunks = page_chunks([0, 1, 2], [400.0, 400.0, 400.0], spacing=30)
    assert chunks == [[0, 1, 2]]


def test_page_chunks_landscape_uses_shorter_page_height() -> None:
    chunks = page_chunks([0, 1], [1200.0, 1200.0], spacing=30, orientation="landscape")
    assert chunks == [[0], [1]]


def test_page_chunks_respects_user_spacing() -> None:
    """Larger spacing forces an earlier page break before footer overflow."""
    heights = [1400.0, 1400.0]
    tight = page_chunks([0, 1], heights, spacing=30, orientation="portrait")
    loose = page_chunks([0, 1], heights, spacing=120, orientation="portrait")
    assert tight == [[0, 1]]
    assert loose == [[0], [1]]


def test_page_chunks_exact_fit_stays_on_one_page() -> None:
    """Segments that exactly fill the content band should not be split."""
    max_px = paste_page_chunk_max_px("portrait")
    spacing = 30
    heights = [1400.0, max_px - 1400.0 - spacing]
    chunks = page_chunks([0, 1], heights, spacing=spacing, orientation="portrait")
    assert chunks == [[0, 1]]


def test_page_chunks_never_exceed_paste_max() -> None:
    heights = [900.0, 850.0, 800.0, 750.0, 700.0]
    spacing = 30.0
    max_px = paste_page_chunk_max_px("portrait")
    chunks = page_chunks(list(range(len(heights))), heights, spacing=spacing)
    for chunk in chunks:
        assert chunk_stack_height_px(chunk, heights, spacing) <= max_px + 1e-6
