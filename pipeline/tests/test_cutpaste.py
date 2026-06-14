from pipeline.cutpaste import build_part_segment_map


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
